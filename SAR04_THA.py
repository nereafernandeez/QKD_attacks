from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from numpy.random import randint
import numpy as np
import math as math
import random
import sys

#SIMULACIÓN DE UN PROTOCOLO SARG04 QUE SUFRE UN ATAQUE THA
#EL CANAL CUÁNTICO ES FIBRA ÓPTICA, POR LO QUE TIENEN EN CUENTA LAS PÉRDIDAS DEL CANAL

#Las funciones que antes tengan una referencia se refieren a que se han tomado del libro de Qiskit. Si no tienen referencia, son de realización propia
#[1] https://github.com/Qiskit/textbook/blob/main/notebooks/ch-algorithms/quantum-key-distribution.ipynb

#Función para validar los parámetros introducidos por el usuario
def validation_parameters(eta_det, n, alpha, l, mu):
    #Condiciones que deben complir el número promedio de fotones, mu (0<mu<0.5) --> acotar en la práctica a (0.01<mu<0.5)
    #Si mu es demasiado pequeño, hay prácticamente tan solo pulsos vacíos 
    if(mu<=0.01):
        sys.exit(f"ERROR:\u03BC demasiado pequeño. Para este \u03BC casi todos los pulsos generado tienen 0 fotones promedio. Valor ingresado: {mu}")
    #Si es demasiado grande el mu, no se considera régimen de pulsos débiles
    if(mu>0.5):
        sys.exit(f"ERROR:\u03BC NO debe ser mayor que 1. ¡Recuerda!, es un pulso coherente débil. Valor ingresado: {mu}")
    #Condiciones que debe cumplir la eficiencia cuántica del detector, eta_det (0<eta_det<1) --> acotar en la práctica a (0.05<eta_det<1)
    if not (0.05<eta_det<=1):
        sys.exit(f"ERROR: \u03B7_det debe estar entre 0.05 y 1. Valor ingresado: {eta_det}")
    #La atenuación de la fibra óptica no puede ser negativa
    if(alpha<0):
        sys.exit(f"ERROR: \u03B1 no puede ser negativo. Valor ingresado: {alpha}")
    #La atenuación de la fibra óptica no puede ser demasiado grande. 
    if(alpha>0.5):
        sys.exit(f"ERROR: \u03B1 no es un valor realista. Demasiada atenuación para ser práctico. Prueba con valores cercanos a 0.25 en unidades de dB/km. Valor ingresado: {alpha}")
    #La distancia no puede ser demasiado pequeña
    if(l<=1):
        sys.exit(f"ERROR: Se requiere una distancia mínima de 1 km. Si no, no tiene sentido hacer un protocolo QKD. Le podrías dar la clave en persona. Prueba con 100 en unidades de km. Valor ingresado: {l}")
    #La distancia no puede ser demasiado grande, no es realista.
    if(l>500):
        sys.exit(f"ERROR: La distancia es demasiado grande. Prueba con 50 en unidades de km. Valor ingresado: {l}")
    #Condición para que haya un número mínimo de bits en la clave final. Con 10 bits antes de destilar, la clave final tendría aproximadamente 3 bits
    if(n<10):
        sys.exit(f"ERROR: n es demasiado pequeño. Prueba a multiplicar por 100 el valor que habías ingresado. Número de bits que llega a Bob tras atenuación de la fibra: {n}")

    return None

#Función que usa Alice para codificar el mensaje que quiere enviar 
def encode_message(bits):
    message = []
    states = []
    #longitud del mensaje de Alice
    n = len(bits)
    for i in range(n):
        #Crear un qubit. Por defecto está en estado |0>
        qc = QuantumCircuit(1,1)
        #Si el bit de Alice vale 0, se codifica en base Z
        if(bits[i]==0):
            #Se escoge de manera aleatoria y uniforme uno de los dos estados posibles dentro de la base
            #Estado |0>
            if(random.random() < 0.5):
                states.append("0")
            #Estado |1>    
            else:
                qc.x(0)
                states.append("1")
        #Si el bit de Alice vale 1, se codifica en base X
        else:
            #Estado |+>
            if(random.random() < 0.5):
                qc.h(0)
                states.append("+")
            #Estado |->
            else:
                qc.x(0)
                qc.h(0)
                states.append("-")
        qc.barrier()
        message.append(qc)
    #Devolver mensaje codificado en qubits y la cadena con los símbolo correspondiente a cada estado
    return message, states

#Función para que Bob escoja de manera aleatoria las bases con las que mide
def bases_choice(n):
    bases = []
    for i in range(n):
        #Selección aleatoria uniforme de la base Z o la base x
        if(random.random() < 0.5):
            bases.append("Z")
        else:
            bases.append("X")
    return bases

#Función para que Bob mida los estados cuánticos enviados por Alice por el canal cuántico [1]
def measure_message(message, bases):
    #longitud de la selección de bases de Bob
    n = len(bases)
    measurements=[]

    for i in range(n):
        #Si el bit aleatorio de la cadena de bases es 0, se mide en base Z, que es la base computacional por defecto
        if(bases[i]=="Z"):
            message[i].measure(0,0)
        #Si el bit es 1, se mide en base X. Se logra pasar desde la base Z hasta la base X mediante una puerta de Hadamard
        else:
            message[i].h(0)
            message[i].measure(0,0)
        #Simulador en un ordenador clásico del comportamiento de un ordenador cuántico
        aer_sim = AerSimulator()
        result = aer_sim.run(message[i], shots=1, memory=True).result()
        measured_bit = int(result.get_memory()[0])
        measurements.append(measured_bit)

    return measurements

#Función para crear los conjuntos de estados que Alice manda por el canal público a Bob para comenzar el proceso de destilación de la clave
def sets_sifting(states):
    n = len(states)
    sets = []

    for i in range(n):
        #Si el estado que ha enviado Alice es |1>
        if(states[i]=="1"):
            #Se crea o bien el conjunto {|1>,|+>} o bien el {|1>,|->}
            sets.append(["1", random.choice(["+", "-"])])
        #Si el estado que ha enviado Alice es |0>
        elif(states[i]=="0"):
            #Se crea o bien el conjunto {|0>,|+>} o bien el {|0>,|->}
            sets.append(["0", random.choice(["+", "-"])])
        #Si el estado que ha enviado Alice es |+>
        elif(states[i]=="+"):
            #Se crea o bien el conjunto {|0>,|+>} o bien el {|1>,|+>}
            sets.append([random.choice(["0", "1"]), "+"])
        #Si el estado que ha enviado Alice es |->
        else:
            #Se crea o bien el conjunto {|0>,|->} o bien el {|1>,|->}
            sets.append([random.choice(["0", "1"]), "-"])

    return sets

#Función con la que Bob intenta adivinar qué estado ha enviado Alice. Siempre parte de la misma idea: si Bob hubiese acertado la base, 
#el estado enviado por Alice lo puede deducir sabiendo la base que ha escogido y el resultado que ha obtenido tras la medida
def states_guess(bases, results):
    #Longitud bases de Bob
    n = len(bases)
    states = []

    for i in range(n):
        #Si ha medido con la base Z y ha obtenido el bit 0, el estado de Alice tendría que ser el |0>
        if(bases[i]=="Z" and results[i]==0):
            states.append("0")
        #Si ha medido con la base Z y ha obtenido el bit 1, el estado de Alice tendría que ser el |1>
        elif(bases[i]=="Z" and results[i]==1):
            states.append("1")
        #Si ha medido con la base X y ha obtenido el bit 0, el estado de Alice tendría que ser el |+>
        elif(bases[i]=="X" and results[i]==0):
            states.append("+")
        #Si ha medido con la base X y ha obtenido el bit 1, el estado de Alice tendría que ser el |->
        else:
            states.append("-")

    return states

#Función para la destilación de las claves de Bob y Alice
def sifted_key(sets_Alice, states_Bob, bits_Alice):
    n = len(states_Bob)
    good_bits_Bob = []
    positions = []
    good_bits_Alice = []

    for i in range(n):
        #Si el estado que ha intentado adivinar Bob pertenece al conjunto de estados que ha enviado Alice, 
        #Bob no puede estar segurode qué estado ha enviado realmente Alice ya que su resultado de la medida puede provenir de ambos estados.
        #Recordar que en cada conjunto, los estados son no ortogonales
        if(states_Bob[i] in sets_Alice[i]):
            pass

        else:
            #Si Bob había adivinado el estado |0>, pero los conjuntos enviados por Alice eran {|1>, |+>} o {|1>, |->}, 
            #sabe que se ha equivocado al medir con la base Z ya que <1|0>=0. 
            #La base correcta era X y añade un bit 1 a su clave
            if(states_Bob[i]=="0" and (sets_Alice[i]==["1", "+"] or sets_Alice[i]==["1", "-"])):
                good_bits_Bob.append(1)
                positions.append(i)
            #Si Bob había adivinado el estado |1>, pero los conjuntos enviados por Alice eran {|0>, |+>} o {|0>, |->}, 
            #sabe que se ha equivocado al medir con la base Z ya que <1|0>=0. 
            #La base correcta era X y añade un bit 1 a su clave
            elif(states_Bob[i]=="1" and (sets_Alice[i]==["0", "+"] or sets_Alice[i]==["0", "-"])):
                good_bits_Bob.append(1)
                positions.append(i)
            #Si Bob había adivinado el estado |+>, pero los conjuntos enviados por Alice eran {|1>, |->} o {|0>, |->}, 
            #sabe que se ha equivocado al medir con la base Z ya que <+|->=0.
            #La base correcta era Z y añade un bit 0 a su clave
            elif(states_Bob[i]=="+" and (sets_Alice[i]==["1", "-"] or sets_Alice[i]==["0", "-"])):
                good_bits_Bob.append(0)
                positions.append(i)
            #Si Bob había adivinado el estado |->, pero los conjuntos enviados por Alice eran {|1>, |+>} o {|0>, |+>}, 
            #sabe que se ha equivocado al medir con la base X ya que <1|0>=0. 
            #La base correcta era Z y añade un bit 0 a su clave
            else:
                good_bits_Bob.append(0)
                positions.append(i)

    for j in range(n):
        #Sabiendo las posiciones con las que se ha podido quedar Bob finalmente, se filtra la clave de Alice
        if j in positions:
            good_bits_Alice.append(bits_Alice[j])

    return good_bits_Bob, good_bits_Alice, positions

#Función para separar una muestra de la clave destilada y calcular el QBER con esa muestra [1]
def sample(key,selection):
    sample = []
    #Para las posiciones aleatorias que conformarán la muestra
    for i in selection:
        #Asegurar que el índice es válido
        i = np.mod(i, len(key))
        #Sacar los bits que están en esas posiciones de la clave final
        sample.append(key.pop(i))

    return sample

#Función con la que, si Eve realiza un ataque THA al selecto de bases de Bob, puede acabar sabiendo la clave final compartida
def key_Eve(bases_Bob, positions):
    n = len(bases_Bob)
    key = []
    final_key=[]

    for i in range(n):
        #Si las base elegida por Bob ha sido Z, Eve se guarda el bit 1, ya que Bob se queda los bits cuando se ha equivocado de 
        #base al medir
        if(bases_Bob[i])=="Z":
            key.append(1)
        #Si las base elegida por Bob ha sido X, Eve se guarda el bit 0, ya que Bob se queda los bits cuando que se ha equivocado de 
        #base al medir
        else:
            key.append(0)
    #Eve puede saber con qué posiciones quedarse ya que Bob le tiene que proporcionar esta información a Alice a través del canal público
    for i in positions:
        final_key.append(key[i])

    return final_key

#Función para calcular el QBER con las cadenas de muestras
def QBER(sample_Alice, sample_Bob):
    error = 0
    n = len(sample_Alice)

    for i in range(n):
        #Si el bit de la muestra de Alice no coincide con el de Bob, hay un error y se suma 1 al contandor
        if (sample_Alice[i] != sample_Bob[i]):
            error+=1
    #El QBER es la cantidad de errores que se han contando en la muestra partido de la longitud de la muestra
    return error/n


try:
    #Parámetros que debe introducir el usuario
    print("")
    mu = float(input("Introduce número promedio de fotones por pulso, \u03BC (Por ejemplo, 0.1) : "))
    eta_det = float(input("Introduce la eficacia del detector, \u03B7_det (Por ejemplo, 0.1) : "))
    n = int(float(input("Introduce el número de bits enviados por Alice (Por ejemplo 1e6, que sería 1000000) : ")))    
    alpha = float(input("Introduce el coeficiente de atenuación de la fibra óptica en unidades de dB/km, \u03B1 (Por ejemplo, 0.25) : "))   
    l = float(input("Introduce la longitud de la fibra óptica en unidades de km (Por ejemplo, 80) : "))
    #Cálculo de la cantidad de bits que sobreviven al pasar por la fibrá óptica que tiene una determinada atenuación y longitud. También se 
    #tiene en cuenta la eficiencia del detector
    #Se toma que Alice envía también esta cantidad porque realmente acaba dando igual
    delta = alpha*l
    R_raw_fibra = eta_det*math.pow(10,-delta/10)*mu
    n_fibra = int(round(R_raw_fibra*n))
    #Validación de los parámetros que se van a emplear en el protocolo
    validation_parameters(eta_det, n_fibra, alpha, l, mu)
    #bits de Alice que quiere enviar a Bob de forma segura
    bits_Alice_tha = randint(2, size=n_fibra)
    #Codificación del mensaje por parte de Alice en estados cuánticos para enviarlos por la fibra óptica
    message_tha, states_Alice_tha = encode_message(bits_Alice_tha)
    #Conjuntos que enviará Alice por el canal público para destilar la clave
    sets_Alice_tha = sets_sifting(states_Alice_tha)
    #Bases aleatorias seleccionadas por Bob para medir el mensaje que le llega por la fibra óptica
    bases_Bob_tha = bases_choice(n_fibra)
    #Resultados que obtiene Bob tras la medida del mensaje
    results_Bob_tha = measure_message(message_tha, bases_Bob_tha)
    #Estados que Bob intenta adivinar como si fuesen los que ha enviado Alice
    states_Bob_tha = states_guess(bases_Bob_tha, results_Bob_tha)
    #Destilación de las claves de Alice y Bob con los estados que intenta adivinar Bob y los conjuntos que le envía Alice
    Bob_key_tha, Alice_key_tha, positions_sift = sifted_key(sets_Alice_tha, states_Bob_tha, bits_Alice_tha.tolist())
    #Eve roba la selección de bases de Bob, por lo que conoce la clave final
    Eve_key_tha = key_Eve(bases_Bob_tha, positions_sift)
    #Se crea una muestra de longitud 1/3 la longitud de las claves destiladas
    sample_size_tha = int(round((1/3)*len(Alice_key_tha),0))
    #Se crea de manera aleatoria las posiciones que se tomarán como muestra
    bit_selection_tha = randint(n_fibra, size=sample_size_tha)
    #Se crea la muestra de Alice, quitándola de la clave final
    Alice_sample_tha = sample(Alice_key_tha, selection=bit_selection_tha)
    #Se crea la muestra de Bob, quitándola de la clave final
    Bob_sample_tha = sample(Bob_key_tha, selection=bit_selection_tha)
    #Se crea la muestra de Eve, quitándola de la clave final
    Eve_sample_tha = sample(Eve_key_tha, selection=bit_selection_tha)
    #Se calcula el error producido en el proceso
    error_tha = QBER(Alice_sample_tha, Bob_sample_tha)

    print("")
    print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
    print("")
    print("¡Ataque THA exitoso!")
    print("")
    print(f"Clave final de Alice = {Alice_key_tha}")
    print(f"Clave final de Bob  = {Bob_key_tha}")
    print(f"Clave robada por Eve = {Eve_key_tha}")
    print("")
    print(f"Longitud de la clave final = {len(Alice_key_tha)}")
    print("")
#Si los parámetros no cumplen las validaciones
except:
    print("")
    #Se muestra el pantalla el error
    validation_parameters(eta_det, n_fibra, alpha, l, mu)
    print("")