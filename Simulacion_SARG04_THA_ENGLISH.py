from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime import SamplerV2 as Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from numpy.random import randint
import numpy as np
import math as math
import random
import sys

# SIMULATION OF A SARG04 PROTOCOL UNDERGOING A THA ATTACK
# THE QUANTUM CHANNEL IS OPTICAL FIBER, SO CHANNEL LOSSES ARE TAKEN INTO ACCOUNT

# Functions preceded by a reference are taken from the Qiskit textbook. 
# Those without a reference are original work.
# [1] https://github.com/Qiskit/textbook/blob/main/notebooks/ch-algorithms/quantum-key-distribution.ipynb

# Function to validate the parameters entered by the user
def validation_parameters(eta_det, n, alpha, l, mu):
    # Conditions for the average number of photons, mu (0 < mu < 0.5) --> practical range (0.01 < mu < 0.5)
    # If mu is too small, there are practically only empty pulses 
    if(mu <= 0.01):
        sys.exit(f"ERROR: \u03BC is too small. For this \u03BC, almost all generated pulses contain an average of 0 photons. Value entered: {mu}")
    # If mu is too large, it is not considered a weak-pulse regime
    if(mu > 0.5):
        sys.exit(f"ERROR: \u03BC must NOT be greater than 0.5. Remember, it is a weak coherent pulse! Value entered: {mu}")
    # Conditions for the detector quantum efficiency, eta_det (0 < eta_det < 1) --> practical range (0.05 < eta_det < 1)
    if not (0.05 < eta_det <= 1):
        sys.exit(f"ERROR: \u03B7_det must be between 0.05 and 1. Value entered: {eta_det}")
    # Fiber optic attenuation cannot be negative
    if(alpha < 0):
        sys.exit(f"ERROR: \u03B1 cannot be negative. Value entered: {alpha}")
    # Fiber optic attenuation cannot be too large
    if(alpha > 0.5):
        sys.exit(f"ERROR: \u03B1 is not a realistic value. Too much attenuation to be practical. Try values close to 0.25 dB/km. Value entered: {alpha}")
    # Distance cannot be too short
    if(l <= 1):
        sys.exit(f"ERROR: A minimum distance of 1 km is required. Otherwise, a QKD protocol is unnecessary; you could hand over the key in person. Try 100 km. Value entered: {l}")
    # Distance cannot be too large; it is not realistic.
    if(l > 500):
        sys.exit(f"ERROR: The distance is too large. Try 50 km. Value entered: {l}")
    # Condition to ensure a minimum number of bits in the final key
    if(n < 10):
        sys.exit(f"ERROR: n is too small. Try multiplying your input by 100. Number of bits reaching Bob after fiber attenuation: {n}")

    return None

# Function used by Alice to encode the message she wants to send 
def encode_message(bits):
    message = []
    states = []
    # Length of Alice's message
    n = len(bits)
    for i in range(n):
        # Create a qubit. Default state is |0>
        qc = QuantumCircuit(1,1)
        # If Alice's bit is 0, it is encoded in the Z basis
        if(bits[i] == 0):
            # One of the two possible states within the basis is chosen randomly and uniformly
            # State |0>
            if(random.random() < 0.5):
                states.append("0")
            # State |1>    
            else:
                qc.x(0)
                states.append("1")
        # If Alice's bit is 1, it is encoded in the X basis
        else:
            # State |+>
            if(random.random() < 0.5):
                qc.h(0)
                states.append("+")
            # State |->
            else:
                qc.x(0)
                qc.h(0)
                states.append("-")
        qc.barrier()
        message.append(qc)
    # Return encoded message in qubits and the string with the corresponding symbols for each state
    return message, states

# Function for Bob to randomly choose the measurement bases
def bases_choice(n):
    bases = []
    for i in range(n):
        # Uniform random selection of Z basis or X basis
        if(random.random() < 0.5):
            bases.append("Z")
        else:
            bases.append("X")
    return bases

# Function for Bob to measure the quantum states sent by Alice via the quantum channel [1]
def measure_message(message, bases):
    service = QiskitRuntimeService(channel='ibm_quantum', token='')
    backend = service.least_busy(operational=True, simulator=False)
    # Length of Bob's basis selection
    n = len(bases)
    measurements = []

    for i in range(n):
        # If the basis bit is Z, measure in the computational basis
        if(bases[i] == "Z"):
            message[i].measure(0,0)
        # If the basis bit is X, use a Hadamard gate to measure in the X basis
        else:
            message[i].h(0)
            message[i].measure(0,0)
            
        sampler = Sampler(mode=backend)
        pm = generate_preset_pass_manager(optimization_level=2, backend=backend)
        isa_circuit = pm.run([message[i]])
        job = sampler.run([isa_circuit], shots=1)

        # Retrieve per-shot measurement
        list_of_results = job.result()[0].data.c.get_bitstrings()
        measurements.append(list_of_results)
    return measurements

# Function to create the sets of states Alice sends via the public channel to start the sifting process
def sets_sifting(states):
    n = len(states)
    sets = []

    for i in range(n):
        # If Alice sent state |1>
        if(states[i] == "1"):
            # Create the set {|1>, |+>} or {|1>, |->}
            sets.append(["1", random.choice(["+", "-"])])
        # If Alice sent state |0>
        elif(states[i] == "0"):
            # Create the set {|0>, |+>} or {|0>, |->}
            sets.append(["0", random.choice(["+", "-"])])
        # If Alice sent state |+>
        elif(states[i] == "+"):
            # Create the set {|0>, |+>} or {|1>, |+>}
            sets.append([random.choice(["0", "1"]), "+"])
        # If Alice sent state |->
        else:
            # Create the set {|0>, |->} or {|1>, |->}
            sets.append([random.choice(["0", "1"]), "-"])

    return sets

# Function where Bob attempts to guess Alice's state
def states_guess(bases, results):
    n = len(bases)
    states = []

    for i in range(n):
        # If measured in Z basis and result is 0, the state should be |0>
        if(bases[i] == "Z" and results[i] == 0):
            states.append("0")
        # If measured in Z basis and result is 1, the state should be |1>
        elif(bases[i] == "Z" and results[i] == 1):
            states.append("1")
        # If measured in X basis and result is 0, the state should be |+>
        elif(bases[i] == "X" and results[i] == 0):
            states.append("+")
        # If measured in X basis and result is 1, the state should be |->
        else:
            states.append("-")

    return states

# Function for the sifting of Alice's and Bob's keys
def sifted_key(sets_Alice, states_Bob, bits_Alice):
    n = len(states_Bob)
    good_bits_Bob = []
    positions = []
    good_bits_Alice = []

    for i in range(n):
        # If the guessed state belongs to Alice's set, Bob is unsure (non-orthogonal states)
        if(states_Bob[i] in sets_Alice[i]):
            pass
        else:
            # SARG04 Logic: If the result is impossible for one of the states in the set, 
            # Bob knows exactly which bit Alice sent.
            if(states_Bob[i] == "0" and (sets_Alice[i] == ["1", "+"] or sets_Alice[i] == ["1", "-"])):
                good_bits_Bob.append(1)
                positions.append(i)
            elif(states_Bob[i] == "1" and (sets_Alice[i] == ["0", "+"] or sets_Alice[i] == ["0", "-"])):
                good_bits_Bob.append(1)
                positions.append(i)
            elif(states_Bob[i] == "+" and (sets_Alice[i] == ["1", "-"] or sets_Alice[i] == ["0", "-"])):
                good_bits_Bob.append(0)
                positions.append(i)
            else:
                good_bits_Bob.append(0)
                positions.append(i)

    for j in range(n):
        if j in positions:
            good_bits_Alice.append(bits_Alice[j])

    return good_bits_Bob, good_bits_Alice, positions

# Function to sample the sifted key and calculate QBER [1]
def sample(key, selection):
    sample = []
    for i in selection:
        i = np.mod(i, len(key))
        sample.append(key.pop(i))
    return sample

# Function for Eve to gain the final key by performing a THA on Bob's basis selection
def key_Eve(bases_Bob, positions):
    n = len(bases_Bob)
    key = []
    final_key = []

    for i in range(n):
        # If Bob chose Z, Eve records 1; if X, Eve records 0
        if(bases_Bob[i]) == "Z":
            key.append(1)
        else:
            key.append(0)
    
    # Eve knows which positions to keep from the public channel announcement
    for i in positions:
        final_key.append(key[i])

    return final_key

# Function to calculate QBER
def QBER(sample_Alice, sample_Bob):
    error = 0
    n = len(sample_Alice)
    for i in range(n):
        if (sample_Alice[i] != sample_Bob[i]):
            error += 1
    return error / n


try:
    # User inputs
    print("")
    mu = float(input("Enter average number of photons per pulse, \u03BC (e.g., 0.1): "))
    eta_det = float(input("Enter detector efficiency, \u03B7_det (e.g., 0.1): "))
    n = int(float(input("Enter the number of bits sent by Alice (e.g., 1e6): ")))    
    alpha = float(input("Enter fiber optic attenuation coefficient in dB/km, \u03B1 (e.g., 0.25): "))   
    l = float(input("Enter the length of the optical fiber in km (e.g., 80): "))

    # Calculation of bits surviving fiber losses and detector efficiency
    delta = alpha * l
    R_raw_fiber = eta_det * math.pow(10, -delta/10) * mu
    n_fiber = int(round(R_raw_fiber * n))

    # Validate parameters
    validation_parameters(eta_det, n_fiber, alpha, l, mu)

    bits_Alice_tha = randint(2, size=n_fiber)
    message_tha, states_Alice_tha = encode_message(bits_Alice_tha)
    sets_Alice_tha = sets_sifting(states_Alice_tha)
    bases_Bob_tha = bases_choice(n_fiber)
    
    results_Bob_tha = measure_message(message_tha, bases_Bob_tha)
    results_tha_Bob_new = [int(elemento[0]) for elemento in results_Bob_tha]
    
    states_Bob_tha = states_guess(bases_Bob_tha, results_tha_Bob_new)
    Bob_key_tha, Alice_key_tha, positions_sift = sifted_key(sets_Alice_tha, states_Bob_tha, bits_Alice_tha.tolist())
    
    # Eve performs THA on Bob's basis choice
    Eve_key_tha = key_Eve(bases_Bob_tha, positions_sift)

    sample_size_tha = int(round((1/3) * len(Alice_key_tha), 0))
    bit_selection_tha = randint(n_fiber, size=sample_size_tha)

    Alice_sample_tha = sample(Alice_key_tha, selection=bit_selection_tha)
    Bob_sample_tha = sample(Bob_key_tha, selection=bit_selection_tha)
    Eve_sample_tha = sample(Eve_key_tha, selection=bit_selection_tha)
    
    error_tha = QBER(Alice_sample_tha, Bob_sample_tha)

    print("")
    print("-" * 150)
    print("")
    print("THA attack successful!")
    print("")
    print(f"Alice's final key = {Alice_key_tha}")
    print(f"Bob's final key   = {Bob_key_tha}")
    print(f"Key stolen by Eve = {Eve_key_tha}")
    print("")
    print(f"Final key length = {len(Alice_key_tha)}")
    print("")

except:
    print("")
    validation_parameters(eta_det, n_fiber, alpha, l, mu)
    print("")