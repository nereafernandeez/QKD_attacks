from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from numpy.random import randint
import numpy as np
import math as math
import random
import sys

#SIMULATION OF A SARG04 PROTOCOL UNDER A THA ATTACK
#THE QUANTUM CHANNEL IS OPTICAL FIBER, SO CHANNEL LOSSES ARE TAKEN INTO ACCOUNT

#Functions that have a reference were taken from the Qiskit textbook. If they don't have a reference, they are original implementations
#[1] https://github.com/Qiskit/textbook/blob/main/notebooks/ch-algorithms/quantum-key-distribution.ipynb

#Function to validate the parameters entered by the user
def validation_parameters(eta_det, n, alpha, l, mu):
    #Conditions that the average photon number mu must satisfy (0<mu<0.5) --> practically restrict to (0.01<mu<0.5)
    #If mu is too small, there are practically only empty pulses
    if(mu<=0.01):
        sys.exit(f"ERROR:\u03BC too small. For this \u03BC almost all generated pulses have 0 average photons. Entered value: {mu}")
    #If mu is too large, it is not considered the weak-pulse regime
    if(mu>0.5):
        sys.exit(f"ERROR:\u03BC MUST NOT be greater than 1. Remember!, it is a weak coherent pulse. Entered value: {mu}")
    #Conditions that the detector quantum efficiency eta_det must satisfy (0<eta_det<1) --> practically (0.05<eta_det<1)
    if not (0.05<eta_det<=1):
        sys.exit(f"ERROR: \u03B7_det must be between 0.05 and 1. Entered value: {eta_det}")
    #Fiber attenuation cannot be negative
    if(alpha<0):
        sys.exit(f"ERROR: \u03B1 cannot be negative. Entered value: {alpha}")
    #Fiber attenuation cannot be too large.
    if(alpha>0.5):
        sys.exit(f"ERROR: \u03B1 is not a realistic value. Too much attenuation to be practical. Try values near 0.25 in dB/km. Entered value: {alpha}")
    #Distance cannot be too small
    if(l<=1):
        sys.exit(f"ERROR: A minimum distance of 1 km is required. Otherwise, it makes no sense to run a QKD protocol. You could give the key in person. Try 100 in km. Entered value: {l}")
    #Distance cannot be too large; not realistic.
    if(l>500):
        sys.exit(f"ERROR: The distance is too large. Try 50 in km. Entered value: {l}")
    #Condition to have a minimum number of bits in the final key. With 10 bits before distillation, the final key would have approximately 3 bits
    if(n<10):
        sys.exit(f"ERROR: n is too small. Try multiplying by 100 the value you entered. Number of bits that reach Bob after fiber attenuation: {n}")

    return None

#Function used by Alice to encode the message she wants to send 
def encode_message(bits):
    message = []
    states = []
    #length of Alice's message
    n = len(bits)
    for i in range(n):
        #Create a qubit. By default it is in state |0>
        qc = QuantumCircuit(1,1)
        #If Alice's bit is 0, encode in Z basis
        if(bits[i]==0):
            #Uniformly choose one of the two possible states within the basis
            #State |0>
            if(random.random() < 0.5):
                states.append("0")
            #State |1>    
            else:
                qc.x(0)
                states.append("1")
        #If Alice's bit is 1, encode in X basis
        else:
            #State |+>
            if(random.random() < 0.5):
                qc.h(0)
                states.append("+")
            #State |->
            else:
                qc.x(0)
                qc.h(0)
                states.append("-")
        qc.barrier()
        message.append(qc)
    #Return the message encoded in qubits and the string with the symbol corresponding to each state
    return message, states

#Function for Bob to randomly choose the bases with which he measures
def bases_choice(n):
    bases = []
    for i in range(n):
        #Uniform random selection of Z basis or X basis
        if(random.random() < 0.5):
            bases.append("Z")
        else:
            bases.append("X")
    return bases

#Function for Bob to measure the quantum states sent by Alice through the quantum channel [1]
def measure_message(message, bases):
    #length of Bob's bases selection
    n = len(bases)
    measurements=[]

    for i in range(n):
        #If the random bit of the bases string is Z, measure in Z basis (computational basis by default)
        if(bases[i]=="Z"):
            message[i].measure(0,0)
        #If the bit is X, measure in X basis. Transition from Z to X is achieved with a Hadamard gate
        else:
            message[i].h(0)
            message[i].measure(0,0)
        #Simulator on a classical computer of a quantum computer's behavior
        aer_sim = AerSimulator()
        result = aer_sim.run(message[i], shots=1, memory=True).result()
        measured_bit = int(result.get_memory()[0])
        measurements.append(measured_bit)

    return measurements

#Function to create the sets of states that Alice sends over the public channel to Bob to begin the key sifting process
def sets_sifting(states):
    n = len(states)
    sets = []

    for i in range(n):
        #If the state Alice sent is |1>
        if(states[i]=="1"):
            #Create either the set {|1>,|+>} or {|1>,|->}
            sets.append(["1", random.choice(["+", "-"])])
        #If the state Alice sent is |0>
        elif(states[i]=="0"):
            #Create either the set {|0>,|+>} or {|0>,|->}
            sets.append(["0", random.choice(["+", "-"])])
        #If the state Alice sent is |+>
        elif(states[i]=="+"):
            #Create either the set {|0>,|+>} or {|1>,|+>}
            sets.append([random.choice(["0", "1"]), "+"])
        #If the state Alice sent is |->
        else:
            #Create either the set {|0>,|->} or {|1>,|->}
            sets.append([random.choice(["0", "1"]), "-"])

    return sets

#Function with which Bob tries to guess which state Alice sent. It always follows the same idea:
#if Bob had guessed the correct basis, the state sent by Alice can be deduced knowing the chosen basis and the measurement result
def states_guess(bases, results):
    #Length of Bob's bases
    n = len(bases)
    states = []

    for i in range(n):
        #If he measured with Z basis and obtained bit 0, Alice's state must have been |0>
        if(bases[i]=="Z" and results[i]==0):
            states.append("0")
        #If he measured with Z basis and obtained bit 1, Alice's state must have been |1>
        elif(bases[i]=="Z" and results[i]==1):
            states.append("1")
        #If he measured with X basis and obtained bit 0, Alice's state must have been |+>
        elif(bases[i]=="X" and results[i]==0):
            states.append("+")
        #If he measured with X basis and obtained bit 1, Alice's state must have been |->
        else:
            states.append("-")

    return states

#Function for sifting Bob's and Alice's keys
def sifted_key(sets_Alice, states_Bob, bits_Alice):
    n = len(states_Bob)
    good_bits_Bob = []
    positions = []
    good_bits_Alice = []

    for i in range(n):
        #If the state Bob tried to guess belongs to the set of states that Alice sent,
        #Bob cannot be sure which state Alice actually sent because his measurement result could come from either state.
        #Remember that in each set, the states are non-orthogonal
        if(states_Bob[i] in sets_Alice[i]):
            pass

        else:
            #If Bob guessed |0>, but the sets sent by Alice were {|1|, |+>} or {|1|, |->},
            #he knows he measured in the wrong basis (Z) since <1|0>=0.
            #The correct basis was X and he adds a bit 1 to his key
            if(states_Bob[i]=="0" and (sets_Alice[i]==["1", "+"] or sets_Alice[i]==["1", "-"])):
                good_bits_Bob.append(1)
                positions.append(i)
            #If Bob guessed |1>, but the sets sent by Alice were {|0|, |+>} or {|0|, |->},
            #he knows he measured in the wrong basis (Z) since <1|0>=0.
            #The correct basis was X and he adds a bit 1 to his key
            elif(states_Bob[i]=="1" and (sets_Alice[i]==["0", "+"] or sets_Alice[i]==["0", "-"])):
                good_bits_Bob.append(1)
                positions.append(i)
            #If Bob guessed |+>, but the sets sent by Alice were {|1|, |->} or {|0|, |->},
            #he knows he measured in the wrong basis (X) since <+|->=0.
            #The correct basis was Z and he adds a bit 0 to his key
            elif(states_Bob[i]=="+" and (sets_Alice[i]==["1", "-"] or sets_Alice[i]==["0", "-"])):
                good_bits_Bob.append(0)
                positions.append(i)
            #If Bob guessed |->, but the sets sent by Alice were {|1|, |+>} or {|0|, |+>},
            #he knows he measured in the wrong basis (X) since <1|0>=0.
            #The correct basis was Z and he adds a bit 0 to his key
            else:
                good_bits_Bob.append(0)
                positions.append(i)

    for j in range(n):
        #Knowing the positions that Bob finally kept, filter Alice's key
        if j in positions:
            good_bits_Alice.append(bits_Alice[j])

    return good_bits_Bob, good_bits_Alice, positions

#Function to separate a sample from the distilled key and compute the QBER with that sample [1]
def sample(key,selection):
    sample = []
    #For the random positions that will form the sample
    for i in selection:
        #Ensure the index is valid
        i = np.mod(i, len(key))
        #Remove the bits at those positions from the final key
        sample.append(key.pop(i))

    return sample

#Function with which, if Eve performs a THA on Bob's basis selection, she can end up knowing the shared final key
def key_Eve(bases_Bob, positions):
    n = len(bases_Bob)
    key = []
    final_key=[]

    for i in range(n):
        #If the base chosen by Bob was Z, Eve records bit 1, because Bob keeps bits when he measured in the wrong
        #basis
        if(bases_Bob[i])=="Z":
            key.append(1)
        #If the base chosen by Bob was X, Eve records bit 0, because Bob keeps bits when he measured in the wrong
        #basis
        else:
            key.append(0)
    #Eve can know which positions to keep because Bob must provide this information to Alice over the public channel
    for i in positions:
        final_key.append(key[i])

    return final_key

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


try:
    #Parameters that the user must enter
    print("")
mu = float(input("Enter the average number of photons per pulse, \u03BC (e.g., 0.1): "))
    eta_det = float(input("Enter the detector efficiency, \u03B7_det (e.g., 0.1): "))
    n = int(float(input("Enter the number of bits sent by Alice (e.g., 1e6, which is 1,000,000): ")))    
    alpha = float(input("Enter the fiber optic attenuation coefficient in units of dB/km, \u03B1 (e.g., 0.25): "))   
    l = float(input("Enter the length of the optical fiber in units of km (e.g., 80): "))
    #Calculation of how many bits survive after passing through the optical fiber which has a certain attenuation and length. Also
    #detector efficiency is taken into account
    #It is assumed Alice also sends this amount because in the end it doesn't matter
    delta = alpha*l
    R_raw_fibra = eta_det*math.pow(10,-delta/10)*mu
    n_fibra = int(round(R_raw_fibra*n))
    #Validation of the parameters to be used in the protocol
    validation_parameters(eta_det, n_fibra, alpha, l, mu)
    #Alice's bits that she wants to send to Bob securely
    bits_Alice_tha = randint(2, size=n_fibra)
    #Encoding of the message by Alice in quantum states to send over the optical fiber
    message_tha, states_Alice_tha = encode_message(bits_Alice_tha)
    #Sets that Alice will send over the public channel to sift the key
    sets_Alice_tha = sets_sifting(states_Alice_tha)
    #Random bases selected by Bob to measure the message arriving through the optical fiber
    bases_Bob_tha = bases_choice(n_fibra)
    #Results obtained by Bob after measuring the message
    results_Bob_tha = measure_message(message_tha, bases_Bob_tha)
    #States Bob tries to guess as if they were those sent by Alice
    states_Bob_tha = states_guess(bases_Bob_tha, results_Bob_tha)
    #Sifting of Alice's and Bob's keys with the states Bob attempts to guess and the sets Alice sends
    Bob_key_tha, Alice_key_tha, positions_sift = sifted_key(sets_Alice_tha, states_Bob_tha, bits_Alice_tha.tolist())
    #Eve steals Bob's basis selection, so she knows the final key
    Eve_key_tha = key_Eve(bases_Bob_tha, positions_sift)
    #Create a sample of length 1/3 of the distilled keys
    sample_size_tha = int(round((1/3)*len(Alice_key_tha),0))
    #Randomly choose the positions that will be taken as the sample
    bit_selection_tha = randint(n_fibra, size=sample_size_tha)
    #Create Alice's sample, removing it from the final key
    Alice_sample_tha = sample(Alice_key_tha, selection=bit_selection_tha)
    #Create Bob's sample, removing it from the final key
    Bob_sample_tha = sample(Bob_key_tha, selection=bit_selection_tha)
    #Create Eve's sample, removing it from the final key
    Eve_sample_tha = sample(Eve_key_tha, selection=bit_selection_tha)
    #Compute the error produced in the process
    error_tha = QBER(Alice_sample_tha, Bob_sample_tha)

    print("")
    print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
    print("")
    print("THA attack successful!")
    print("")
    print(f"Alice's final key = {Alice_key_tha}")
    print(f"Bob's final key  = {Bob_key_tha}")
    print(f"Key stolen by Eve = {Eve_key_tha}")
    print("")
    print(f"Length of the final key = {len(Alice_key_tha)}")
    print("")
#If parameters do not pass the validations
except:
    print("")
    #Show the error on screen
    validation_parameters(eta_det, n_fibra, alpha, l, mu)
    print("")