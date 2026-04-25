from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime import SamplerV2 as Sampler, QiskitRuntimeService
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from numpy.random import randint
import numpy as np
import math as math
import random
import sys

#SIMULATION OF A BB84 PROTOCOL UNDER A PNS ATTACK
#THE POSSIBLE DEFENSE AGAINST A PNS ATTACK USING THE DECOY-STATE METHOD IS ALSO SIMULATED
#THE QUANTUM CHANNEL IS OPTICAL FIBER, SO CHANNEL LOSSES ARE TAKEN INTO ACCOUNT

#Functions that have a reference were taken from the Qiskit textbook. If they don't have a reference, they are original implementations
#[1] https://github.com/Qiskit/textbook/blob/main/notebooks/ch-algorithms/quantum-key-distribution.ipynb

#Function to validate the parameters entered by the user
def validate_parameters(mu, n, eta_det, alpha):
    #Conditions that the average photon number mu must satisfy (0<mu<0.5) --> practically restrict to (0.01<mu<0.5)
    #If mu is too small, there are practically only empty pulses
    if(mu <= 0.01):
        sys.exit(f"ERROR: \u03BC is too small. For this \u03BC, almost all generated pulses contain an average of 0 photons. Value entered: {mu}")
    
    # If mu is too large, it is not considered the weak-pulse regime
    if(mu > 0.5):
        sys.exit(f"ERROR: \u03BC must NOT be greater than 0.5. Remember, it is a weak coherent pulse! Value entered: {mu}")
    
    # Conditions that the detector quantum efficiency eta_det must satisfy (0 < eta_det < 1) --> practically (0.05 < eta_det < 1)
    if not (0.05 < eta_det <= 1):
        sys.exit(f"ERROR: \u03B7_det must be between 0.05 and 1. Value entered: {eta_det}")
    
    # Fiber attenuation cannot be negative
    if(alpha < 0):
        sys.exit(f"ERROR: \u03B1 cannot be negative. Value entered: {alpha}")
    
    # Fiber attenuation cannot be too large.
    if(alpha > 0.5):
        sys.exit(f"ERROR: \u03B1 is not a realistic value. Too much attenuation to be practical. Try values close to 0.25 dB/km. Value entered: {alpha}")
    
    # Condition to have a minimum number of bits in the final key. With 10 bits before distillation, the final key would have approximately 3 bits
    if(n < 10):
        sys.exit(f"ERROR: n is too small. Try multiplying the value you entered by 100. Number of bits reaching Bob after fiber attenuation: {n}")
    return None

#Function to validate the parameters used in the decoy-state method
def decoy_validations(mu_decoy, percent_decoy, percent_signal):
    #if the decoy mu is greater than one, it would not be in the weak-pulse regime
    if(mu_decoy > 1):
        sys.exit(f"ERROR. \u03BC_decoy cannot be greater than 1. It must be a weak pulse. Value entered: {mu_decoy}")
    
    # For this implementation of the decoy-state method mu_decoy must be greater than 0
    if(mu_decoy < 0.1):
        sys.exit(f"ERROR. \u03BC_decoy is too small. Value entered: {mu_decoy}")
    
    # If the difference between mu_decoy and mu_signal is not large enough, the detection statistics won't be significantly affected
    if(abs(mu_decoy - mu) < 0.1):
        sys.exit(f"ERROR. The difference between \u03BC_decoy and \u03BC_signal must be larger for the statistics to be affected. Try \u03BC_decoy = {mu_decoy + 0.2}. Value entered: \u03BC_decoy = {mu_decoy}, while \u03BC_signal = {mu}")
    
    # If there are too many decoy states, the protocol is inefficient because decoy states do not form part of the final key
    if (percent_decoy > 50):
        sys.exit(f"ERROR. There must be a lower percentage of decoy states than signal states so the protocol is not too inefficient. The final key is formed only by signal states, not decoy states. Value entered: {percent_decoy}")
    
    # A maximum limit of 95% signal states is set so there is at least 5% decoy states
    if(percent_signal > 95):
        sys.exit(f"ERROR. You cannot have 100% signal states since the decoy-state method would not be in use. Try 80% signal states and 20% decoy states. Value entered: {percent_signal}")
    
    # If the sum of percentages of signal and decoy states does not equal 100, it makes no sense
    if (percent_signal + percent_decoy != 100):
        sys.exit(f"ERROR. The sum of the percentages for signal and decoy states must equal 100%. Try 80% signal states and 20% decoy states. Values entered: decoy percentage = {percent_decoy} and signal percentage = {percent_signal}")
    return None

#Function used by Alice to encode the message she wants to send [1]
def encode_message(bits,bases):
    message = []
    #length of Alice's message
    n = len(bases) 

    for i in range(n):
        #Create a qubit. By default it is in state |0>
        qc = QuantumCircuit(1,1)
        #encode in state |0|
        if (bases[i] == bits[i] == 0):
            pass
        #encode in state |1|
        elif (bases[i] == 0 and bits[i] == 1 ):
            qc.x(0)
        #encode in state |+>
        elif (bases[i] == 1 and bits[i] == 0):
            qc.h(0)
        #encode in state |->
        elif (bases[i] == bits[i] == 1):
            qc.x(0)
            qc.h(0)
        qc.barrier()
        message.append(qc)

    return message

#Function used by Bob to measure the qubits that arrive through the quantum channel [2]
def measure_message(message, base):
    #length of the message to measure
    n = len(base)
    measurements=[]

    service = QiskitRuntimeService(channel='ibm_quantum', token='')
    backend = service.least_busy(operational=True, simulator=False)

    for i in range(n):
        #If the random bit of the bases string is 0, measure in Z basis (computational basis by default)
        if(base[i]==0):
            message[i].measure(0,0)
        #If the bit is 1, measure in X basis. Transition from Z to X is achieved with a Hadamard gate
        else:
            message[i].h(0)
            message[i].measure(0,0)
        #sampler = Sampler(mode=backend)
        sampler = Sampler(mode=backend)
        pm = generate_preset_pass_manager(optimization_level=2, backend=backend)
        isa_circuit = pm.run([message[i]])
        job = sampler.run([isa_circuit], shots=1)

        # retrieve per-shot measurement
        list_of_results = job.result()[0].data.c.get_bitstrings()
        measurements.append(list_of_results)
    return measurements

#Function for the distillation of the shared key between Alice and Bob [2]
def remove_garbage(bases_A, bases_B, bits):
    #length of the strings 
    n = len(bits)
    good_bits=[] 
    
    for i in range(n):
        #If the basis bits match, keep the bits that belong to the final key string
        if (bases_A[i] == bases_B[i]):
            good_bits.append(bits[i])
            
    return good_bits

#Function for the special distillation of the shared key for the decoy-state method. Decoy states
#are randomly distributed through the sent message and they are represented by 2 and 3, which correspond to bits 
#0 and 1 in the signal states
def remove_garbage_decoy(bases_A, bases_B, bits, positions):
    n = len(bits)
    good_bits=[] 
    #If the basis bits match, keep the bits that belong to the final key string. 
    # Additionally, Alice tells Bob the positions of decoy states. Values of bits at those positions are changed
    for i in range(n):
        if (bases_A[i] == bases_B[i]):
            #If it is a decoy state
            if i in positions:
                if(bits[i]==0):
                    #Convert 0 to 2 
                    bits[i]=2
                else:
                    #Convert 1 to 3
                    bits[i]=3
            good_bits.append(bits[i])

    return good_bits

#Function to separate a sample from the distilled key and compute the QBER with that sample [2]
def sample(key,selection):
    sample = []
    #For the random positions that will form the sample
    for i in selection:
        #Ensure the index is valid
        i = np.mod(i, len(key))
        #Remove the bits at those positions from the final key
        sample.append(key.pop(i))

    return sample

#Function to compute the QBER with the sample strings
def QBER(sample_Alice, sample_Bob):
    error = 0
    n = len(sample_Alice)

    for i in range(n):
        #If Alice's sample bit does not match Bob's, count an error
        if (sample_Alice[i] != sample_Bob[i]):
            error+=1
    #QBER is the number of errors counted in the sample divided by the sample length
    return error/n

#Function to compute the yield of decoy states
def yield_decoy_method(Bob_key):
    n = len(Bob_key)
    yield_decoy = 0

    for i in range(n):
        #Decoy states take values 2 and 3 to differentiate from signal states, so count how many appear in Bob's key
        if(Bob_key[i]==2 or Bob_key[i]==3):
            yield_decoy+=1
    #The yield of signal states is the total states that arrive to Bob minus the decoy yield
    yield_signal = n - yield_decoy
    #Yields are calculated as the number of states Bob receives of each type divided by the total number of states he receives
    return yield_decoy/n, yield_signal/n

#Function to keep only the bits coming from signal states in the final key
def key_signal_states(key):
    n = len(key)
    final_key = []

    for i in range(n):
        #Bits of signal states are 0 and 1, while bits of decoy states are 2 and 3
        if(key[i]==0 or key[i]==1):
            final_key.append(key[i])
        else:
            pass

    return final_key

#Function to compute the probability of finding n photons in a coherent pulse
def probability_photons(n,mu):
    #Poisson distribution
    P = (math.pow(mu,n)*math.exp(-mu))/(math.factorial(n))

    return P

#Function to ask the user if they want to use the decoy-state method knowing the protocol is vulnerable to a PNS attack by Eve
def ask_user():
    while True:
        print("")
        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
answer = input("Eve has performed a PNS attack on your BB84 protocol. Do you wish to protect the protocol using the decoy-state method? (yes/no): ").strip().lower()
        print("")
        #If the user wants to implement it
        if(answer=="yes"):
            #Call the function that runs the decoy-state method
            estados_señuelo()
            break

        elif(answer=="no"):
            print("")
            print("Eve has successfully stolen the key :/")
            print("")
            break

        else:
            print("")
            print("Invalid response. Don't get creative; you just need to answer yes or no")

#Function to implement the decoy-state method and detect a PNS attack
def estados_señuelo():
    print("")
    print(f"For the implementation of the decoy-state method, the parameter entered at the beginning of the program will be used as \u03BC_signal; that is, \u03BC_signal = {mu}")
    print(f"The initial number of bits entered at the beginning of the program is also used.")
    print("")
    try:
        # SITUATION 1) Eve tries to perform a PNS attack but Alice and Bob employ the decoy-state method along with BB84    

        # Parameters entered by the user
        mu_decoy = float(input(f"Enter the average number of photons for the decoy states (For example, if \u03BC_signal = {mu}, then \u03BC_decoy = {mu+0.4}): "))
        percent_decoy = int(input(f"Enter the percentage of states you want to be decoy states. Without the '%' symbol (For example, 30): "))
        percent_signal = int(input(f"Enter the percentage of states you want to be signal states. Without the '%' symbol (For example, 70): ")) #Validate the entered parameters
        decoy_validations(mu_decoy, percent_decoy, percent_signal)
        #Probability of finding 0 photons for pulses with decoy states
        P_0_decoy = probability_photons(0, mu_decoy)
        #Probability of finding 1 photon for pulses with decoy states
        P_1_decoy = probability_photons(1, mu_decoy)
        #Probability of finding 2 or more photons for pulses with decoy states
        P_2_or_more_decoy = 1 - P_0_decoy - P_1_decoy
        #Normalize the probability of finding a multiphoton pulse since vacuum pulses are not used
        P_2_or_more_nor_decoy = (P_2_or_more_decoy)/(P_1_decoy + P_2_or_more_decoy)
        #Fraction of signal states used in the method
        frac_signal = percent_signal/100
        #Fraction of decoy states used in the method
        frac_decoy = percent_decoy/100
        #Number of bits that will come from decoy states
        n_decoy = int(round(frac_decoy*n,0))
        #Number of bits that will come from signal states
        n_signal = int(round(frac_signal*n,0))
        #Number of bits that will come from a multiphoton pulse that contains decoy states. Eve performed a PNS attack,
        #so she only lets multiphoton pulses pass
        n_2_decoy = int(round(P_2_or_more_nor_decoy*n_decoy,0))
        #Number of bits that will come from a multiphoton pulse that contains signal states. Eve performed a PNS attack,
        #so she only lets multiphoton pulses pass
        n_2_signal = int(round(P_2_or_more_nor*n_signal,0))
        #Calculation of how many bits survive after passing through the optical fiber which has a certain attenuation and length. 
        #Detector efficiency is also taken into account. 
        #It is assumed that Alice also sends this amount because in the end it doesn't matter
        R_raw_decoy = eta_det*P_2_or_more_decoy
        n_2_decoy_fibra = int(round(R_raw_decoy*n_2_decoy,0))
        n_2_signal_fibra = int(round(R_raw_pns*n_2_signal,0))
        #Bits Alice wants to send that will end up being decoy states
        bits_decoy_Alice = randint(low=2, high=4, size=n_2_decoy_fibra)
        bits_decoy_Alice = bits_decoy_Alice.tolist()
        #Bits Alice wants to send that will end up being signal states. These bits are the ones that will form the shared private key
        bits_signal_Alice = randint(2, size=n_2_signal_fibra)
        bits_signal_Alice = bits_signal_Alice.tolist()
        #Total bits that Alice encodes
        bits_method_Alice = bits_signal_Alice + bits_decoy_Alice
        #Mix the decoy and signal bits randomly
        random.shuffle(bits_method_Alice)
        bits_method_Alice = np.array(bits_method_Alice)

        position_method = []
        #Store the positions where decoy states are located
        for i in range(len(bits_method_Alice)):
            if(bits_method_Alice[i]==2):
                position_method.append(i)
                #Change them to bits 0 and 1 to reuse the encoding function.
                #Also, during decoding Bob can only measure 0 and 1
                bits_method_Alice[i]=0

            elif(bits_method_Alice[i]==3):
                position_method.append(i)
                bits_method_Alice[i]=1
        #Random bases of Alice 
        bases_method_Alice = randint(2, size=n_2_decoy_fibra+n_2_signal_fibra) 
        #Alice's message encoding
        message_method = encode_message(bits_method_Alice, bases_method_Alice)
        #Random bases of Bob to measure the message
        bases_method_Bob = randint(2, size=n_2_decoy_fibra+n_2_signal_fibra) 
        #Resulting bits obtained by Bob
        results_method_Bob = measure_message(message_method, bases_method_Bob)
        results_method_Bob_new = [int(elemento[0]) for elemento in results_method_Bob]
        #This would be Eve's PNS attack with the photons stolen from multiphoton pulses
        message_method = encode_message(bits_method_Alice, bases_method_Alice)
        #Wait until Alice and Bob share their bases
        bases_method_Eve = bases_method_Bob
        #Eve's results after the PNS attack
        results_method_Eve = measure_message(message_method, bases_method_Eve)
        results_method_Eve_new = [int(elemento[0]) for elemento in results_method_Eve]
        #Distillation of Alice's final key
        Alice_key_method = remove_garbage_decoy(bases_method_Alice, bases_method_Bob, bits_method_Alice.tolist(), position_method)
        #Distillation of Bob's final key
        Bob_key_method = remove_garbage_decoy(bases_method_Alice, bases_method_Bob, results_method_Bob_new, position_method)
        #Distillation of Eve's final key. This is no longer PNS, simply Alice and Bob publicly share the bases they used
        Eve_key_method = remove_garbage_decoy(bases_method_Alice, bases_method_Eve, results_method_Eve_new, position_method)
        #Yield of decoy and signal states that reach Bob
        yield_decoy_Bob, yield_signal_Bob = yield_decoy_method(Bob_key_method)
        #Create a sample of length 1/3 of the distilled keys
        sample_size_method = int(round((1/3)*len(Alice_key_method),0))
        #Randomly choose the positions that will be taken as the sample
        bit_selection_method = randint(n_2_decoy_fibra+n_2_signal_fibra, size=sample_size_method)
        #Create Alice's sample, removing it from the final key
        Alice_sample_method = sample(Alice_key_method, selection=bit_selection_method)
        #Create Bob's sample, removing it from the final key
        Bob_sample_method = sample(Bob_key_method, selection=bit_selection_method)
        #Create Eve's sample, removing it from the final key
        Eve_sample_method = sample(Eve_key_method, selection=bit_selection_method)
        #Remove from the final key the bits that came from decoy states
        Alice_final_key_method = key_signal_states(Alice_key_method)
        #Remove from the final key the bits that came from decoy states
        Bob_final_key_method = key_signal_states(Bob_key_method)
        #Remove from the final key the bits that came from decoy states
        Eve_final_key_method = key_signal_states(Eve_key_method)
        #Compute the error produced in the process
        error_method = QBER(Alice_sample_method, Bob_sample_method)
        
        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print("PNS attack detected using the decoy-state method!")
        print("")
        print(f"Alice's final key = {Alice_final_key_method}")
        print(f"Bob's final key = {Bob_final_key_method}")
        print(f"Key stolen by Eve = {Eve_final_key_method}")
        print("")
        print(f"Key length without decoy states = {len(Alice_final_key_method)}")
        print(f"Key length with decoy states = {len(Alice_key_method)}")
        print("")
        print(f"QBER = {np.round(error_method*100,2)} %")
        print("")
        print("The decoy state yield is suspicious!")
        print("")
        print(f"Decoy state yield = {np.round(yield_decoy_Bob*100,2)} %")
        print(f"Signal state yield = {np.round(yield_signal_Bob*100,2)} %")

        #SITUATION 2)Compare with the statistics that would occur when applying the decoy-state method without a PNS attack

        #Normalize the probability of finding a 1-photon pulse since vacuum pulses are not used
        P_1_nor_decoy = (P_1_decoy)/(P_1_decoy + P_2_or_more_decoy)
        #Number of bits coming from a 1-photon pulse that will end up as decoy states
        n_1_decoy = int(round(P_1_nor_decoy*n_decoy,0))
        #Number of bits coming from a 1-photon pulse that will end up as signal states
        n_1_signal = int(round(P_1_nor*n_signal,0))
        #Calculation of how many bits survive after passing through the optical fiber which has a certain attenuation and length.
        #Detector efficiency is also taken into account
        R_raw_BB84 = eta_det*math.pow(10,-delta_BB84/10)*mu
        R_raw_BB84_decoy = eta_det*math.pow(10,-delta_BB84/10)*mu_decoy
        #Number of bits that actually reach Bob. It is assumed Alice also sends this amount because it does not matter in the end
        n_decoy_fibra_no_pns = int(round(R_raw_BB84_decoy*(n_2_decoy+n_1_decoy),0))
        n_signal_fibra_no_pns = int(round(R_raw_BB84*(n_2_signal+n_1_signal),0))
        #Bits Alice wants to send that will end up being decoy states
        bits_decoy_Alice_no_pns = randint(low=2, high=4, size=n_decoy_fibra_no_pns)
        bits_decoy_Alice_no_pns = bits_decoy_Alice_no_pns.tolist()
        #Bits Alice wants to send that will end up being signal states
        bits_signal_Alice_no_pns = randint(2, size=n_signal_fibra_no_pns)
        bits_signal_Alice_no_pns = bits_signal_Alice_no_pns.tolist()
        #Total bits that Alice encodes
        bits_method_Alice_no_pns = bits_signal_Alice_no_pns + bits_decoy_Alice_no_pns
        #Mix the decoy and signal bits randomly
        random.shuffle(bits_method_Alice_no_pns)
        bits_method_Alice_no_pns = np.array(bits_method_Alice_no_pns)

        position_method_no_pns = []
        #Store the positions where decoy states are located
        for i in range(len(bits_method_Alice_no_pns)):
            if(bits_method_Alice_no_pns[i]==2):
                #Change them to bits 0 and 1 to reuse the encoding function.
                #Also, during decoding Bob can only measure 0 and 1
                position_method_no_pns.append(i)
                bits_method_Alice_no_pns[i]=0

            elif(bits_method_Alice_no_pns[i]==3):
                position_method_no_pns.append(i)
                bits_method_Alice_no_pns[i]=1
        #Random bases of Alice 
        bases_method_Alice_no_pns = randint(2, size=n_decoy_fibra_no_pns+n_signal_fibra_no_pns) 
        #Alice's message encoding
        message_method_no_pns = encode_message(bits_method_Alice_no_pns, bases_method_Alice_no_pns)
        #Random bases of Bob to measure the message
        bases_method_Bob_no_pns = randint(2, size=n_decoy_fibra_no_pns+n_signal_fibra_no_pns) 
        #Resulting bits obtained by Bob
        results_method_Bob_no_pns = measure_message(message_method_no_pns, bases_method_Bob_no_pns)
        results_method_Bob_no_pns_new = [int(elemento[0]) for elemento in results_method_Bob_no_pns]
        #Distillation of Alice's final key
        Alice_key_method_no_pns = remove_garbage_decoy(bases_method_Alice_no_pns, bases_method_Bob_no_pns, bits_method_Alice_no_pns.tolist(), position_method_no_pns)
        #Distillation of Bob's final key
        Bob_key_method_no_pns = remove_garbage_decoy(bases_method_Alice_no_pns, bases_method_Bob_no_pns, results_method_Bob_no_pns, position_method_no_pns)
        #Yield of decoy and signal states that reach Bob
        yield_decoy_Bob_no_pns, yield_signal_Bob_no_pns = yield_decoy_method(Bob_key_method_no_pns)

        print("")
        print("This is the expected range:")
        print("")
        print(f"Decoy state yield without PNS attack   = {np.round(yield_decoy_Bob_no_pns*100,2)} %")
        print(f"Signal state yield without PNS attack  = {np.round(yield_signal_Bob_no_pns*100,2)} %")
        print("")
    #If parameters do not pass the validations
    except:
        print("")
        #Show the error on screen
        decoy_validations(mu_decoy, percent_decoy, percent_signal)
        print("")


try:
    print("")
    #Parameters entered by the user
 mu = float(input("Enter the average number of photons per pulse, \u03BC (e.g., 0.1): "))
    eta_det = float(input("Enter the detector efficiency, \u03B7_det (e.g., 0.1): "))
    n = int(float(input("Enter the number of bits sent by Alice (e.g., 1e6, which is 1,000,000): ")))    
    alpha = float(input("Enter the fiber optic attenuation coefficient in units of dB/km, \u03B1 (e.g., 0.25): "))

    #Probability of finding 0 photons
    P_0 = probability_photons(0, mu)
    #Probability of finding 1 photon
    P_1 = probability_photons(1, mu)
    #Probability of finding 2 or more photons
    P_2_or_more = 1 - P_0 - P_1
    #Normalize the probability of finding a 1-photon pulse since vacuum pulses are not used
    P_1_nor = (P_1)/(P_1 + P_2_or_more)
    #Normalize the probability of finding a multiphoton pulse since vacuum pulses are not used
    P_2_or_more_nor = (P_2_or_more)/(P_1 + P_2_or_more)
    #Number of bits that will come from a multiphoton pulse 
    n_pns = int(round(P_2_or_more_nor*n,0))

    #First calculate the distance from which a PNS attack can be performed:
    #Rate after attack = Rate Bob would expect from BB84 protocol

    #Minimum attenuation of the BB84 protocol in optical fiber so that Eve's intervention is not detected
    delta_BB84 = 10*math.log10(mu/P_2_or_more)
    #Optical fiber length that meets the minimum attenuation
    l_BB84 = delta_BB84/alpha
    #Raw detection rate at Bob, which is the rate after the attack
    R_raw_pns = eta_det*P_2_or_more
    #Number of bits that reach Bob after Eve's PNS attack and the attenuation suffered by the qubits in the optical fiber
    n_pns_fibra = int(round(R_raw_pns*n_pns,0))
    #Validate parameters 
    validate_parameters(mu, n_pns_fibra, eta_det, alpha)

print("")
    print("Valid parameters!")

    print("")
    print(f"A PNS attack can be performed for optical fibers with a length of {np.round(l_BB84,2)} km or more using weak pulses with \u03BC = {mu}")
    print("")
    print(f"Starting PNS attack for an optical fiber with attenuation \u03B1 = {alpha} dB/km and length l = {np.round(l_BB84,2)} km")

    #Start BB84 protocol with PNS attack

    #Random string containing the key Alice wants to send
    bits_pns_Alice = randint(2, size=n_pns_fibra)
    #Random string for selecting Alice's encoding bases
    bases_pns_Alice = randint(2, size=n_pns_fibra)
    #Encoding the message in quantum states
    message_pns = encode_message(bits_pns_Alice, bases_pns_Alice)
    #Random string of Bob's measurement bases
    bases_pns_Bob = randint(2, size=n_pns_fibra)
    #String of results after Bob's measurement
    results_pns_Bob = measure_message(message_pns, bases_pns_Bob)
    results_pns_Bob_new  = [int(elemento[0]) for elemento in results_pns_Bob]
    #Simulation to perform Eve's PNS attack. Eve had stored the quantum states from multiphoton pulses in 
    #a quantum memory
    message_pns = encode_message(bits_pns_Alice, bases_pns_Alice)
    #Eve knows the bases that were used to measure because she waited for the public discussion of the bases
    bases_pns_Eve = bases_pns_Bob
    #Eve's result string after the PNS attack
    results_pns_Eve = measure_message(message_pns, bases_pns_Eve)
    results_pns_Eve_new  = [int(elemento[0]) for elemento in results_pns_Eve]
    #Distillation of Alice's key via the public channel
    Alice_key_pns = remove_garbage(bases_pns_Alice, bases_pns_Bob, bits_pns_Alice.tolist())
    #Distillation of Bob's key via the public channel
    Bob_key_pns = remove_garbage(bases_pns_Alice, bases_pns_Bob, results_pns_Bob_new)
    #Eve knows all the information exchanged over the public channel
    Eve_key_pns = remove_garbage(bases_pns_Alice, bases_pns_Eve, results_pns_Eve_new)
    #Create a sample of length 1/3 of the distilled keys
    sample_size_pns = int(round((1/3)*len(Alice_key_pns),0))
    #Randomly choose the positions that will be taken as the sample
    bit_selection_pns = randint(n_pns_fibra, size=sample_size_pns)
    #Create Alice's sample, removing it from the final key
    Alice_sample_pns = sample(Alice_key_pns, selection=bit_selection_pns)
    #Create Bob's sample, removing it from the final key
    Bob_sample_pns = sample(Bob_key_pns, selection=bit_selection_pns)
    #Create Eve's sample, removing it from the final key
    Eve_sample_pns = sample(Eve_key_pns, selection=bit_selection_pns)
    #Compute the QBER generated after the protocol
    error_pns = QBER(Alice_sample_pns, Bob_sample_pns)

    print("")
    print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
    print("")
    print("PNS attack successful!")
    print("")
    print(f"Alice's final key = {Alice_key_pns}")
    print(f"Bob's final key   = {Bob_key_pns}")
    print(f"Key stolen by Eve = {Eve_key_pns}")
    print("")
    print(f"Final key length = {len(Alice_key_pns)}")
    print("")
    print(f"QBER = {np.round(error_pns*100,2)} %")
    
except:
    print("")
    validate_parameters(eta_det, n_pns_fibra, alpha, mu)
    print("")

ask_user()