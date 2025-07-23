from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from numpy.random import randint
import numpy as np
import math as math
import random
import sys

#SIMULACIÓN DE UN PROTOCOLO BB84 QUE SUFRE UN ATAQUE PNS
#TAMBIÉN SE SIMULA LA POSIBLE DEFENSA CONTRA UN ATAQUE PNS MEDIANTE EL MÉTODO DE ESTADOS SEÑUELO
#EL CANAL CUÁNTICO ES FIBRA ÓPTICA, POR LO QUE TIENEN EN CUENTA LAS PÉRDIDAS DEL CANAL

#Las funciones que antes tengan una referencia se refieren a que se han tomado del libro de Qiskit. Si no tienen referencia, son de realización propia
#[1] https://github.com/Qiskit/textbook/blob/main/notebooks/ch-algorithms/quantum-key-distribution.ipynb

#Función para validar los parámetros introducidos por el usuario
def validate_parameters(mu, n, eta_det, alpha):
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
    #Condición para que haya un número mínimo de bits en la clave final. Con 10 bits antes de destilar, la clave final tendría aproximadamente 3 bits
    if(n<10):
        sys.exit(f"ERROR: n es demasiado pequeño. Prueba a multiplicar por 100 el valor que habías ingresado. Número de bits que llega a Bob tras atenuación de la fibra: {n}")

    return None

#Función para validar los parámetros empleados en el método de estados señuelo
def decoy_validations(mu_decoy, percent_decoy, percent_signal):
    #si la mu_señuelo es mayor que uno, no estaría en el régimen de pulsos débiles
    if(mu_decoy>1):
        sys.exit(f"ERROR. \u03BC_señuelo no puede ser mayor que 1. Debe ser un pulso débil. Valor ingresado: {mu_decoy}")
    #Para esta implementación del método de estado señuelo mu_señuelo tiene que ser mayor que 0
    if(mu_decoy<0.1):
        sys.exit(f"ERROR. \u03BC_señuelo demasiado pequeño. Valor ingresado: {mu_decoy}")
    #Si la diferencia entre la mu_señuelo y la mu_señal no es lo suficientemente grande, no se ve afectada casi la estadística de alcances
    if(abs(mu_decoy-mu)<0.1):
        sys.exit(f"ERROR. La diferencia entre \u03BC_señuelo y \u03BC_señal debe ser mayor para que se vea afectada la estadística. Prueba con \u03BC_señuelo = {mu_decoy+0.2}. Valor ingresado: \u03BC_señuelo = {mu_decoy}, mientras que \u03BC_señal = {mu}")
    #Si hay demasiado estados señuelo, el protocolo es ineficiente ya que los estados señuelo no pertenecen a la clave final
    if (percent_decoy>50):
        sys.exit(f"ERROR. Debe haber menos porcentaje de estados señuelo que de estados señal para que el protocolo no sea demasiado ineficiente. La clave final se forma solo con los estados señal, no los señuelo. Valor ingresado: {percent_decoy}")
    #Se pone un límite máximo de 95% estados señal para que haya al menos un 5% de estados señuelo
    if(percent_signal>95):
        sys.exit(f"ERROR. No puede haber un 100% de estados señal ya que no se estaría usando el método de estados señuelo. Prueba con 80% estados señal y 20% estados señuelo. Valor ingresado: {percent_signal}")
    #Si la suma de porcentaje de estados señal y estados señuelo no da 100, no tiene sentido
    if (percent_signal+percent_decoy!=100):
        sys.exit(f"ERROR. La suma de porcentajes entre estados señal y estados señuelo debe dar 100%. Prueba con 80% estados señal y 20% estados señuelo. Valores ingresados: porcentaje señuelo={percent_decoy} y porcentaje señal={percent_signal}")

    return None

#Función que usa Alice para codificar el mensaje que quiere enviar [1]
def encode_message(bits,bases):
    message = []
    #longitud del mensaje de Alice
    n = len(bases) 

    for i in range(n):
        #Crear un qubit. Por defecto está en estado |0>
        qc = QuantumCircuit(1,1)
        #codificar en estado |0>
        if (bases[i] == bits[i] == 0):
            pass
        #codificar en estado |1>
        elif (bases[i] == 0 and bits[i] == 1 ):
            qc.x(0)
        #codificar en estado |+>
        elif (bases[i] == 1 and bits[i] == 0):
            qc.h(0)
        #codificar en estado |->
        else:
            qc.x(0)
            qc.h(0)
        qc.barrier()
        message.append(qc)

    return message

#Función que usa Bob para medir los qubits que le llegan por el canal cuántico [1]
def measure_message(message, base):
    #longitud del mensaje a medir
    n = len(base)
    measurements=[]

    for i in range(n):
        #Si el bit aleatorio de la cadena de bases es 0, se mide en base Z, que es la base computacional por defecto
        if(base[i]==0):
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

#Función para la destilación de la clave compartida entre Alice y Bob [1]
def remove_garbage(bases_A, bases_B, bits):
    #longitud de las cadenas 
    n = len(bits)
    good_bits=[] 
    
    for i in range(n):
        #Si los bits de las bases coinciden, se guardan los bits de la cadena que contiene la clave final
        if (bases_A[i] == bases_B[i]):
            good_bits.append(bits[i])
            
    return good_bits

#Función para la destilación de la clave compartida especial para el método de estados señuelo. Los estados señuelo
#están repartidos aleatoriamente por el mensaje enviado y además están conformados por 2 y 3, que corresponderían a los bits 
#0 y 1 en el estado señal
def remove_garbage_decoy(bases_A, bases_B, bits, positions):
    n = len(bits)
    good_bits=[] 
    #Si los bits de las bases coincides, se guardan los bits de la cadena que contiene la clave final. 
    # Además, Alice le dice a Bob en qué posiciones están los estados señuelo. Se cambian los valores de los bits en esas posiciones
    for i in range(n):
        if (bases_A[i] == bases_B[i]):
            #Si es un estado señuelo
            if i in positions:
                if(bits[i]==0):
                    #Convertir 0 en 2 
                    bits[i]=2
                else:
                    #Convertir 1 en 3
                    bits[i]=3
            good_bits.append(bits[i])

    return good_bits

#Función para separar una muestra de la clave destilada y calcular el QBER con esa muestra [2]
def sample(key,selection):
    sample = []
    #Para las posiciones aleatorias que conformarán la muestra
    for i in selection:
        #Asegurar que el índice es válido
        i = np.mod(i, len(key))
        #Sacar los bits que están en esas posiciones de la clave final
        sample.append(key.pop(i))

    return sample

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

#Función para calcular alcance de los estados señuelo
def yield_decoy_method(Bob_key):
    n = len(Bob_key)
    yield_decoy = 0

    for i in range(n):
        #Los estados señuelo toman valores 2 y 3 para diferenciarse de los estados de la señal, por lo que se cuenta cuántos hay en la 
        #clave de Bob
        if(Bob_key[i]==2 or Bob_key[i]==3):
            yield_decoy+=1
    #El alcance de los estados señal será la resta de los estados totales que le llegan a Bob menos el alcance de estados señuelo
    yield_signal = n - yield_decoy
    #Los alcances se calculan como la cantidad de estados que recibe Bob de cada tipo entre la cantidad total de estados que recibe
    return yield_decoy/n, yield_signal/n

#Función para quedarse en la clave final tan solo con los bits que vienen de los estados señal
def key_signal_states(key):
    n = len(key)
    final_key = []

    for i in range(n):
        #Los bits de los estados señuelo son 0 y 1, mientras que los bits de los estados señuelo son 2 y 3
        if(key[i]==0 or key[i]==1):
            final_key.append(key[i])
        else:
            pass

    return final_key

#Función para calcular la probabilidad de ecnontrar n fotones en un pulso coherente
def probability_photons(n,mu):
    #Distribución de Poisson
    P = (math.pow(mu,n)*math.exp(-mu))/(math.factorial(n))

    return P

#Función para preguntar al usuario si desea emplear el método de estados señuelo sabiendo que el protocolo es vulnerable a un ataque PNS de Eve
def ask_user():
    while True:
        print("")
        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        answer = input("Eve ha realizado un ataque PNS a tu protocolo BB84. ¿Deseas proteger el protocolo con el método de estados señuelo? (si/no): ").strip().lower()
        print("")
        #Si se desea implementar
        if(answer=="si"):
            #Se llama a la función que ejecuta el método de estados señuelo
            estados_señuelo()
            break

        elif(answer=="no"):
            print("")
            print("Eve ha conseguido robar la clave :/")
            print("")
            break

        else:
            print("")
            print("Respuesta no válida. No te pongas creativo, solo tienes que responder 'si' o 'no'. Sin las comillas.")

#Función para implementar el método de estados señuelo y detectar un ataque PNS
def estados_señuelo():
    print("")
    print(f"Para la implementación del método de estados señuelo, se usará como \u03BC_señal el parámetro introducido al principio del programa, es decir \u03BC_señal = {mu}")
    print(f"También se emplea en número de bits iniciales introducidos al principio del programa")
    print("")
    try:
        #SITUACIÓN 1) Eve trata de realizar un ataque PNS pero Alice y Bob emplean el método de estados señuelo junto con el protocolo BB84    

        #Parámetros introducidos por el usuario
        mu_decoy=float(input(f"Introduce el número promedio de fotones para los estados señuelo (Por ejemplo, si \u03BC_señal = {mu}, entonces \u03BC_señuelo = {mu+0.4}) : "))
        percent_decoy=int(input(f"Introduce el porcentaje de estados que quieres que sean señuelo. Sin el símbolo '%' (Por ejemplo, 30) : "))
        percent_signal=int(input(f"Introduce el porcentaje de estados que quieres que sean señal. Sin el símbolo '%' (Por ejemplo, 70) : "))
        #Validar los parámetros introducidos
        decoy_validations(mu_decoy, percent_decoy, percent_signal)
        #Probabilidad de encontrar 0 fotones para los pulsos con estados señuelo
        P_0_decoy = probability_photons(0, mu_decoy)
        #Probabilidad de encontrar 1 fotón para los pulsos con estados señuelo
        P_1_decoy = probability_photons(1, mu_decoy)
        #Probabilidad de encontrar 2 o más fotones para los pulsos con estados señuelo
        P_2_or_more_decoy = 1 - P_0_decoy - P_1_decoy
        #Normalizar la probabilidad de encontrar pulso multifotónico ya que los pulsos sin fotones no se emplean
        P_2_or_more_nor_decoy = (P_2_or_more_decoy)/(P_1_decoy + P_2_or_more_decoy)
        #Fracción de estados señal que se usa en el método
        frac_signal = percent_signal/100
        #Fracción de estados señuelo que se usa en el método
        frac_decoy = percent_decoy/100
        #Cantidad de bits que provendrán de estados señuelo
        n_decoy = int(round(frac_decoy*n,0))
        #Cantidad de bits que provendrán de estados señal
        n_signal = int(round(frac_signal*n,0))
        #Cantidad de bits que provendrán de un pulso multifotónico que contiene estados señuelo. Eve ha realizado ataque PNS, 
        #por lo que solo deja pasar pulsos multifotónicos
        n_2_decoy = int(round(P_2_or_more_nor_decoy*n_decoy,0))
        #Cantidad de bits que provendrán de un pulso multifotónico que contiene estados señal. Eve ha realizado ataque PNS,
        #por lo que solo deja pasar pulsos multifotónicos
        n_2_signal = int(round(P_2_or_more_nor*n_signal,0))
        #Cálculo de la cantidad de bits que sobreviven al pasar por la fibrá óptica que tiene una determinada atenuación y longitud. 
        #También se tiene en cuenta la eficiencia del detector. 
        #Se toma que Alice envía también esta cantidad porque realmente acaba dando igual
        R_raw_decoy = eta_det*P_2_or_more_decoy
        n_2_decoy_fibra = int(round(R_raw_decoy*n_2_decoy,0))
        n_2_signal_fibra = int(round(R_raw_pns*n_2_signal,0))
        #Bits que Alice quiere enviar que acabarán siendo estados señuelo
        bits_decoy_Alice = randint(low=2, high=4, size=n_2_decoy_fibra)
        bits_decoy_Alice = bits_decoy_Alice.tolist()
        #Bits que Alice quiere enviar que acabarán siendo estados señal. Estos bits son los que conformará la clave privada compartida
        bits_signal_Alice = randint(2, size=n_2_signal_fibra)
        bits_signal_Alice = bits_signal_Alice.tolist()
        #Bits totales que Alice codifica
        bits_method_Alice = bits_signal_Alice + bits_decoy_Alice
        #Se mezclan los bits de estados señuelo y señal de manera aleatoria
        random.shuffle(bits_method_Alice)
        bits_method_Alice = np.array(bits_method_Alice)

        position_method = []
        #Se guardan las posiciones donde hay estados señuelo
        for i in range(len(bits_method_Alice)):
            if(bits_method_Alice[i]==2):
                position_method.append(i)
                #Se cambian a bits 0 y 1 para reusar la función de codificación.
                #Además, en la parte de descodificación Bob solo puede medir 0 y 1
                bits_method_Alice[i]=0

            elif(bits_method_Alice[i]==3):
                position_method.append(i)
                bits_method_Alice[i]=1
        #Bases aleatorias de Alice 
        bases_method_Alice = randint(2, size=n_2_decoy_fibra+n_2_signal_fibra) 
        #Codificación del mensaje de Alice
        message_method = encode_message(bits_method_Alice, bases_method_Alice)
        #Bases aleatorias de Bob para medir el mensaje
        bases_method_Bob = randint(2, size=n_2_decoy_fibra+n_2_signal_fibra) 
        #Bits resultantes que obtiene Bob
        results_method_Bob = measure_message(message_method, bases_method_Bob)
        #Esto sería el ataque PNS de Eve con los fotones robados de los pulsos multifotónicos
        message_method = encode_message(bits_method_Alice, bases_method_Alice)
        #Espera a que Alice y Bob compartan sus bases
        bases_method_Eve = bases_method_Bob
        #Resultados de Eve tras el ataque PNS
        results_method_Eve = measure_message(message_method, bases_method_Eve)
        #Destilación de la clave final de Alice
        Alice_key_method = remove_garbage_decoy(bases_method_Alice, bases_method_Bob, bits_method_Alice.tolist(), position_method)
        #Destilación de la clave final de Bob
        Bob_key_method = remove_garbage_decoy(bases_method_Alice, bases_method_Bob, results_method_Bob, position_method)
        #Destilación de la clave final de Eve. Esto ya no es PNS, simplemente Alice y Bob comparten públicamente las bases que han usado
        Eve_key_method = remove_garbage_decoy(bases_method_Alice, bases_method_Eve, results_method_Eve, position_method)
        #Alcande de los estados señuelo y estados señal que llegan a Bob
        yield_decoy_Bob, yield_signal_Bob = yield_decoy_method(Bob_key_method)
        #Se crea una muestra de longitud 1/3 la longitud de las claves destiladas
        sample_size_method = int(round((1/3)*len(Alice_key_method),0))
        #Se crea de manera aleatoria las posiciones que se tomarán como muestra
        bit_selection_method = randint(n_2_decoy_fibra+n_2_signal_fibra, size=sample_size_method)
        #Se crea la muestra de Alice, quitándola de la clave final
        Alice_sample_method = sample(Alice_key_method, selection=bit_selection_method)
        #Se crea la muestra de Bob, quitándola de la clave final
        Bob_sample_method = sample(Bob_key_method, selection=bit_selection_method)
        #Se crea la muestra de Eve, quitándola de la clave final
        Eve_sample_method = sample(Eve_key_method, selection=bit_selection_method)
        #Se quita de la clave final los bits que venían de estados señuelo
        Alice_final_key_method = key_signal_states(Alice_key_method)
        #Se quita de la clave final los bits que venían de estados señuelo
        Bob_final_key_method = key_signal_states(Bob_key_method)
        #Se quita de la clave final los bits que venían de estados señuelo
        Eve_final_key_method = key_signal_states(Eve_key_method)
        #Se calcula el error producido en el proceso
        error_method = QBER(Alice_sample_method, Bob_sample_method)
        
        print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print("¡Ataque PNS detectado con método de estados señuelo!")
        print("")
        print(f"Clave final de Alice = {Alice_final_key_method}")
        print(f"Clave final de Bob = {Bob_final_key_method}")
        print(f"Clave robada por Eve = {Eve_final_key_method}")
        print("")
        print(f"Longitud de la clave sin estados señuelo= {len(Alice_final_key_method)}")
        print(f"Longitud de la clave con estados señuelo= {len(Alice_key_method)}")
        print("")
        print(f"QBER = {np.round(error_method*100,2)} %")
        print("")
        print("¡El alcance de los estados señuelo es sospechoso!")
        print("")
        print(f"Alcance estados señuelo = {np.round(yield_decoy_Bob*100,2)} %")
        print(f"Alcance estados señal = {np.round(yield_signal_Bob*100,2)} %")

        #SITUACIÓN 2)Comparar con la estadística que saldría al aplicar método de estados señuelo sin ataque PNS

        #Normalizar la probabilidad de encontrar pulso con 1 fotón ya que los pulsos sin fotones no se emplean
        P_1_nor_decoy = (P_1_decoy)/(P_1_decoy + P_2_or_more_decoy)
        #Cantidad de bits que vienen de pulso con 1 fotón y acabrán siendo estados señuelo
        n_1_decoy = int(round(P_1_nor_decoy*n_decoy,0))
        #Cantidad de bits que vienen de pulso con 1 fotón y acabrán siendo estados señal
        n_1_signal = int(round(P_1_nor*n_signal,0))
        #Cálculo de la cantidad de bits que sobreviven al pasar por la fibrá óptica que tiene una determinada atenuación y longitud.
        #También se tiene en cuenta la eficiencia del detector
        R_raw_BB84 = eta_det*math.pow(10,-delta_BB84/10)*mu
        R_raw_BB84_decoy = eta_det*math.pow(10,-delta_BB84/10)*mu_decoy
        #Cantidad de bits que realmente llega a Bob. Se toma que Alice envía también esta cantidad porque realmente acaba dando igual
        n_decoy_fibra_no_pns = int(round(R_raw_BB84_decoy*(n_2_decoy+n_1_decoy),0))
        n_signal_fibra_no_pns = int(round(R_raw_BB84*(n_2_signal+n_1_signal),0))
        #Bits que Alice quiere enviar que acabarán siendo estados señuelo
        bits_decoy_Alice_no_pns = randint(low=2, high=4, size=n_decoy_fibra_no_pns)
        bits_decoy_Alice_no_pns = bits_decoy_Alice_no_pns.tolist()
        #Bits que Alice quiere enviar que acabarán siendo estados señal
        bits_signal_Alice_no_pns = randint(2, size=n_signal_fibra_no_pns)
        bits_signal_Alice_no_pns = bits_signal_Alice_no_pns.tolist()
        #Bits totales que Alice codifica
        bits_method_Alice_no_pns = bits_signal_Alice_no_pns + bits_decoy_Alice_no_pns
        #Se mezclan los bits de estados señuelo y señal de manera aleatoria
        random.shuffle(bits_method_Alice_no_pns)
        bits_method_Alice_no_pns = np.array(bits_method_Alice_no_pns)

        position_method_no_pns = []
        #Se guardan las posiciones donde hay estados señuelo
        for i in range(len(bits_method_Alice_no_pns)):
            if(bits_method_Alice_no_pns[i]==2):
                #Se cambian a bits 0 y 1 para reusar la función de codificación.
                #Además, en la parte de descodificación Bob solo puede medir 0 y 1
                position_method_no_pns.append(i)
                bits_method_Alice_no_pns[i]=0

            elif(bits_method_Alice_no_pns[i]==3):
                position_method_no_pns.append(i)
                bits_method_Alice_no_pns[i]=1
        #Bases aleatorias de Alice 
        bases_method_Alice_no_pns = randint(2, size=n_decoy_fibra_no_pns+n_signal_fibra_no_pns) 
        #Codificación del mensaje de Alice
        message_method_no_pns = encode_message(bits_method_Alice_no_pns, bases_method_Alice_no_pns)
        #Bases aleatorias de Bob para medir el mensaje
        bases_method_Bob_no_pns = randint(2, size=n_decoy_fibra_no_pns+n_signal_fibra_no_pns) 
        #Bits resultantes que obtiene Bob
        results_method_Bob_no_pns = measure_message(message_method_no_pns, bases_method_Bob_no_pns)
        #Destilación de la clave final de Alice
        Alice_key_method_no_pns = remove_garbage_decoy(bases_method_Alice_no_pns, bases_method_Bob_no_pns, bits_method_Alice_no_pns.tolist(), position_method_no_pns)
        #Destilación de la clave final de Bob
        Bob_key_method_no_pns = remove_garbage_decoy(bases_method_Alice_no_pns, bases_method_Bob_no_pns, results_method_Bob_no_pns, position_method_no_pns)
        #Alcande de los estados señuelo y estados señal que llegan a Bob
        yield_decoy_Bob_no_pns, yield_signal_Bob_no_pns = yield_decoy_method(Bob_key_method_no_pns)

        print("")
        print("Este es el alcance que se espera:")
        print("")
        print(f"Alcance estados señuelo sin ataque PNS = {np.round(yield_decoy_Bob_no_pns*100,2)} %")
        print(f"Alcance estados señal sin ataque PNS  = {np.round(yield_signal_Bob_no_pns*100,2)} %")
        print("")
    #Si los parámetros no cumplen las validaciones
    except:
        print("")
        #Se muestra el pantalla el error
        decoy_validations(mu_decoy, percent_decoy, percent_signal)
        print("")


try:
    print("")
    #Parámetros introducidos por el usuario
    mu = float(input("Introduce número promedio de fotones por pulso, \u03BC (Por ejemplo, 0.1) : "))
    eta_det = float(input("Introduce la eficacia del detector, \u03B7_det (Por ejemplo, 0.1) : "))
    n = int(float(input("Introduce el número de bits enviados por Alice (Por ejemplo 1e6, que sería 1000000) : ")))    
    alpha = float(input("Introduce el coeficiente de atenuación de la fibra óptica en unidades de dB/km, \u03B1 (Por ejemplo, 0.25) : "))   

    #Probabilidad de encontrar 0 fotones
    P_0 = probability_photons(0, mu)
    #Probabilidad de encontrar 1 fotón
    P_1 = probability_photons(1, mu)
    #Probabilidad de encontrar 2 o más fotones
    P_2_or_more = 1 - P_0 - P_1
    #Normalizar la probabilidad de encontrar pulso con 1 fotón ya que los pulsos sin fotones no se emplean
    P_1_nor = (P_1)/(P_1 + P_2_or_more)
    #Normalizar la probabilidad de encontrar pulso multifotónico ya que los pulsos sin fotones no se emplean
    P_2_or_more_nor = (P_2_or_more)/(P_1 + P_2_or_more)
    #Cantidad de bits que provendrán de un pulso multifotónico 
    n_pns = int(round(P_2_or_more_nor*n,0))

    #Primero calcular la distacia a partir de la que se puede hacer ataque PNS :
    #Tasa después de ataque = Tasa que Bob esperaría por protocolo BB84

    #Atenuación mínima del protocolo BB84 en fibra óptica para que no se detecte la intervención de Eve
    delta_BB84 = 10*math.log10(mu/P_2_or_more)
    #Longitud de fibra óptica que cumple con la atenuación mínima 
    l_BB84 = delta_BB84/alpha
    #Tasa cruda de detección de Bob, que es la tasa después del ataque
    R_raw_pns = eta_det*P_2_or_more
    #Número de bits llegan a Bob después del ataque PNS de Eve y de la atenuación que sufren los qubits por la fibra óptica
    n_pns_fibra = int(round(R_raw_pns*n_pns,0))
    #Validar parámetros 
    validate_parameters(mu, n_pns_fibra, eta_det, alpha)

    print("")
    print("¡Parámetros válidos!")

    print("")
    print(f"Se podrá realizar un ataque PNS para fibras ópticas de longitud {np.round(l_BB84,2)} km o más usando pulsos débiles con \u03BC = {mu}")
    print("")
    print(f"Comienza ataque PNS para una fibra óptica con atenuación \u03B1 = {alpha} dB/km y longitud l = {np.round(l_BB84,2)} km")

    #Inicia el protocolo BB84 con ataque PNS

    #Cadena aleatoria que contiene la clave que quiere enviar Alice
    bits_pns_Alice = randint(2, size=n_pns_fibra)
    #Cadena aleatoria para selección de bases de codificación de Alice
    bases_pns_Alice = randint(2, size=n_pns_fibra)
    #Codificación del mensaje en estados cuánticos
    message_pns = encode_message(bits_pns_Alice, bases_pns_Alice)
    #Cadena aleatoria de bases de medida de Bob
    bases_pns_Bob = randint(2, size=n_pns_fibra)
    #Cadena de resultados tras la medida de Bob
    results_pns_Bob = measure_message(message_pns, bases_pns_Bob)
    #Simulación para hacer el ataque PNS de Eve. Eve tenía guardados los estados cuánticos que vienen de los pulsos multifotónicos en 
    #una memoria cuántica
    message_pns = encode_message(bits_pns_Alice, bases_pns_Alice)
    #Eve sabe las bases que se han empleado para medir porque ha esperado a la discusión pública de las bases
    bases_pns_Eve = bases_pns_Bob
    #Cadena de resultados de Eve tras ataque PNS
    results_pns_Eve = measure_message(message_pns, bases_pns_Eve)
    #Destilación de la clave de Alice mediante el canal público 
    Alice_key_pns = remove_garbage(bases_pns_Alice, bases_pns_Bob, bits_pns_Alice.tolist())
    #Destilación de la clave de Alice mediante el canal público 
    Bob_key_pns = remove_garbage(bases_pns_Alice, bases_pns_Bob, results_pns_Bob)
    #Eve conoce toda la información que se intercambie por el canal público
    Eve_key_pns = remove_garbage(bases_pns_Alice, bases_pns_Eve, results_pns_Eve)
    #Se crea una muestra de longitud 1/3 la longitud de las claves destiladas
    sample_size_pns = int(round((1/3)*len(Alice_key_pns),0))
    #Se crea de manera aleatoria las posiciones que se tomarán como muestra
    bit_selection_pns = randint(n_pns_fibra, size=sample_size_pns)
    #Se crea la muestra de Alice, quitándola de la clave final
    Alice_sample_pns = sample(Alice_key_pns, selection=bit_selection_pns)
    #Se crea la muestra de Bob, quitándola de la clave final
    Bob_sample_pns = sample(Bob_key_pns, selection=bit_selection_pns)
    #Se crea la muestra de Eve, quitándola de la clave final
    Eve_sample_pns = sample(Eve_key_pns, selection=bit_selection_pns)
    #Se calcula el QBER generado tras el protocolo
    error_pns = QBER(Alice_sample_pns, Bob_sample_pns)

    print("")
    print("-------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
    print("")
    print("¡Ataque PNS exitoso!")
    print("")
    print(f"Clave final de Alice = {Alice_key_pns}")
    print(f"Clave final de Bob  = {Bob_key_pns}")
    print(f"Clave robada por Eve = {Eve_key_pns}")
    print("")
    print(f"Longitud de la clave final = {len(Alice_key_pns)}")
    print("")
    print(f"QBER = {np.round(error_pns*100,2)} %")
    
except:
    print("")
    validate_parameters(eta_det, n_pns_fibra, alpha, mu)
    print("")

ask_user()