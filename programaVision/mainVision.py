import socket
import threading
import time
import cv2
import torch
import numpy as np
from matplotlib import pyplot as plt
import ctypes
import os
import math
import socket
import sys
import select
import threading
import struct


class direcionesIP:
    agente   = ("192.168.20.14",1435)#enviar
    interfaz = ("192.168.20.14",1406)#enviar
    #agente   = ("169.254.12.14",1435)#enviar
    #interfaz = ("169.254.12.14",1406)#enviar
    visionAgente = ("0.0.0.0",1436)#recibir
    visioninterfaz = ("0.0.0.0",1434)#recibir

print(" ")
print(f"Enviar a Ip Agente: {direcionesIP.agente}, ip interfaz: {direcionesIP.interfaz}")
print(f"Recibir a puerto Agente: {direcionesIP.visionAgente[1]}, puerto interfaz: {direcionesIP.visioninterfaz[1]}")
print(" ")


class comandoVision:
    def __init__(self, comando, Npiezas, array=None):
        self.comando = comando
        self.Npiezas = Npiezas
        # Si no se proporciona un array, inicializar con arrays de 5 dimensiones llenos de ceros
        self.array = array if array is not None else np.zeros((Npiezas, 5), dtype=float)

    def serialize(self):
        # El formato de la estructura es un tipoComando seguido de un entero Npiezas y luego 5 floats por cada pieza
        narray = 5*self.Npiezas
        formato = "ii" + "f" * narray#* (5 * self.Npiezas)
        # Aplanar la lista de listas para que sea un solo array de floats
        flat_array = self.array.flatten()
        # Empaquetar los datos en formato binario
        return struct.pack(formato, self.comando, self.Npiezas, *flat_array)

    @classmethod
    def deserialize(cls, data):
        # Primero desempaquetar los dos primeros enteros
        int_format = "ii"
        int_size = struct.calcsize(int_format)
        comando, Npiezas = struct.unpack(int_format, data[:int_size])
        # Luego desempaquetar los floats, que son 5 por cada pieza
        float_format = "f" * (5 * Npiezas)
        floats = struct.unpack(float_format, data[int_size:])
        # Convertir el array plano de floats en una lista de listas
        array = np.array(floats).reshape((Npiezas, 5))
        return cls(comando, Npiezas, array)

# Apartado para la visualización de fotos
indice_actual = 0
carpeta = r'D:\YOLO-domino\data\TEST'

ret = calibrar = False

real_width  = 1.71 # Largo real mm
real_height = 1.71 # Ancho real mm a 405mm

# Variable global para almacenar los datos recibidos
data_recv = ""
frame = ""
lock = threading.Lock()

#Cargar Red Neuronal

model = torch.hub.load('yolov5', 'custom', path='yolov5/runs/train/exp16/weights/best.pt', source='local')  # local repo
#model = torch.hub.load('yolov5', 'custom', path='yolov5/yolov5m.pt', source='local') #cargar modelos base

# Config
model.conf = 0.50  # Umbral de confianza para el filtrado de detecciones después de la supresión no máxima (NMS)
#model.iou = 0.45  # Umbral de intersección sobre unión (IoU) para el proceso de NMS
model.agnostic = False  # Supresión no máxima agnóstica respecto a las clases
model.multi_label = False  # NMS multiple labels per box
#model.classes = [6,13,19,24,28,31,33]  # (optional list) filter by class, i.e. = [0, 15, 16] for COCO persons, cats and dogs
model.max_det = 1000  # Máximo número de detecciones por imagen
model.amp = False  # Activar la Precisión Mixta Automática (AMP) durante la inferencia

def px_mm(x, y,z=405):
    global real_height
    global real_width

    xmm = x / real_width
    ymm = y / real_height
    return xmm, ymm

def obtener_imagenes_en_carpeta(carpeta):
    imagenes = []
    for archivo in os.listdir(carpeta):
        if archivo.endswith('.jpg') or archivo.endswith('.png') or archivo.endswith('.jpeg'):
            imagenes.append(archivo)
    imagenes.sort()
    return imagenes

def mostrar_imagen(imagen_path):
    imagen = cv2.imread(imagen_path)
    cv2.imshow('Imagen', imagen)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def angulo_fichas(centros_nums, fichas_guardadas):
    Nfichas = np.size(fichas_guardadas, 0)
    angulos = np.zeros(shape=(Nfichas))

    for i in range(Nfichas):
        pos0 = int(fichas_guardadas[i][0])
        pos1 = int(fichas_guardadas[i][1])
        x = centros_nums[pos1][0] - centros_nums[pos0][0]
        y = centros_nums[pos1][1] - centros_nums[pos0][1]
        angulos[i] = math.atan2(y, x)
        if centros_nums[pos1][0] > centros_nums[pos0][0]:
            angulos[i] = 180 - angulos[i]

    return angulos

def punto_medio_fichas(array_Agente, nPiezas, results_sorted, zona, width):
    nP =0
    pos_piezas   = np.zeros(shape=(nPiezas,4))    #Valores de posición de las piezas
    
    if zona == 0:
        calibx = 522.80
        caliby = 123.11
        z = 530.71
    elif zona == 1:
        calibx = 522.80
        caliby = -66.43
        z = 530.71
    else:
        calibx = -217.42
        caliby = 351.51
        z = 530.71
    

    #cálculo de número de piezas y números
    for i in range(np.size(results_sorted['name'])): #Determinamos número de piezas y números para darle el tamaño requerido a los arrays
        if (results_sorted['name'][i] == 'Domino-Pieces'):
            pos_piezas[nP][0]=results_sorted['xmin'][i]     #Colocamos el xmin en la primera posición
            pos_piezas[nP][1]=results_sorted['xmax'][i]     #Colocamos el xmax en la segunda posición
            pos_piezas[nP][2]=results_sorted['ymin'][i]     #Colocamos el ymin en la tercera posición
            pos_piezas[nP][3]=results_sorted['ymax'][i]     #Colocamos el ymax en la cuarta posición
            nP = nP +1

    for i in range(nPiezas):#CAmbiado##################
        array_Agente[i][3] = ((pos_piezas[i][0] + pos_piezas[i][1])/2)
        array_Agente[i][2] = ((pos_piezas[i][2] + pos_piezas[i][3])/2)
        
        if zona != 99:
            array_Agente[i][3] = 320-((pos_piezas[i][0] + pos_piezas[i][1])/2)
            array_Agente[i][2] = ((pos_piezas[i][2] + pos_piezas[i][3])/2)-240
            array_Agente[i][3] = calcular_distancia_x(array_Agente[i][3],calibx,zona)
            array_Agente[i][2] = calcular_distancia_y(array_Agente[i][2],caliby,zona)
        
    return array_Agente

def calcular_dimencion_real(z, width, xmax, xmin, calibx):
    alpha = 60  # Ángulo de apertura de la cámara
    betaRad = math.radians(alpha / 2)
    dimension_real = calibx - ((float(z) + 30.3213232) * 2 * (xmax - xmin) * math.tan(betaRad)) / (1.62286 * width)
    return dimension_real

def calcular_distancia_x(x_med, calibx, zona):
    if zona == 0:
        print('x: ', x_med / real_width, 'Calibración: ', calibx)
        x = calibx + x_med / real_width
    elif zona == 1:
        print('Pixeles: ', x_med, 'Calibración: ', calibx)
        x = calibx - x_med / real_width
    else:
        print('Pixeles: ', x_med, 'Calibración: ', calibx)
        x = -(calibx + x_med / real_width)
    return x

def calcular_distancia_y(y_med, caliby,zona):
    if  zona == 0:
        print ('y: ', y_med/real_width, ' Calibración: ', caliby)
        y = caliby + y_med / real_width
    elif zona == 1:
        print ('Pixeles: ', y_med, ' Calibración: ', caliby)
        y = caliby - y_med / real_width
    else:
        print ('Pixeles: ', y_med, ' Calibración: ', caliby)
        y = -(caliby + y_med / real_width)
    return y
def calcular_punto_medio(resultados_ordenados, array_Agente):
    puntos_por_id = {}
    nP = 0
    for index, fila in resultados_ordenados.iterrows():
        name = fila['name']
        if name == 'Domino-Pieces':
            id_ = len(puntos_por_id) + 1
            xmin = fila['xmin']
            xmax = fila['xmax']
            ymin = fila['ymin']
            ymax = fila['ymax']
            Nnum = 0
            if id_ not in puntos_por_id:
                puntos_por_id[id_] = {'numeros': []}
            for index2, fila2 in resultados_ordenados.iterrows():
                if fila2['name']!= 'Domino-Pieces':
                    x_medio = int((fila2['xmin'] + fila2['xmax']) / 2)
                    y_medio = int((fila2['ymin'] + fila2['ymax']) / 2)
                    confidence = round(fila2['confidence'], 2)
                    if xmin < x_medio < xmax and ymin < y_medio < ymax and Nnum <= 1:
                        xmm,ymm = px_mm(x_medio,y_medio)
                        puntos_por_id[id_]['numeros'].append({"x": x_medio, "y": y_medio, "numero": fila2['name'], "confidence": confidence})
                        array_Agente[nP][Nnum] = int(fila2['name'])
                        Nnum = Nnum + 1
                        if (Nnum == 2):
                            Nnum = 0
            nP = nP + 1

    return puntos_por_id, array_Agente

def dibujar_lineas(imagen, puntos_por_id, array_Agente, nPiezas):
    angulos = {}
    ang_rad = np.zeros(shape=(nPiezas, 1))
    n = 0
    for id_, info in puntos_por_id.items():
        numeros = info['numeros']
        if not numeros:  # Verificar si la lista de números está vacía
            continue  # Pasar a la siguiente iteración del bucle si no hay números
        numeros_ordenados = sorted(numeros, key=lambda x: x['x'])
        
        # Obtener el primer y último punto de la línea
        try:
            punto_inicial = (numeros_ordenados[0]['x'], numeros_ordenados[0]['y'])
            punto_final = (numeros_ordenados[-1]['x'], numeros_ordenados[-1]['y'])
        except IndexError:
            continue  # Pasar a la siguiente iteración del bucle si no hay suficientes números
        
        cv2.line(imagen, punto_inicial, punto_final, (0, 255, 0), 2)
        
        # Calcular el ángulo entre la línea y el eje X
        dx = punto_final[0] - punto_inicial[0]
        dy = punto_final[1] - punto_inicial[1]
        angulo_rad = np.arctan2(dy, dx)

        angulo_grados = np.degrees(angulo_rad)
        angulo_grados = round(angulo_grados, 2)
        if punto_final[1] > punto_inicial[1]:
            if punto_final[0] > punto_inicial[0]:
                angulo_grados = 180 - angulo_grados
        else:
            if punto_final[0] > punto_inicial[0]:
                angulo_grados = -angulo_grados

        # Almacenar el ángulo asociado a cada ID
        angulos[id_] = angulo_grados
        # Agregar el ángulo al diccionario existente puntos_por_id
        info['angulo'] = angulo_grados
        # Agregamos al array que se enviará al agente el ángulo
        array_Agente[n][4] = angulo_rad
        n = n + 1

    return imagen, angulos, puntos_por_id, array_Agente

def Lectura_YoloP(frame, instruccion,zona=99):

    global z 
    height, width, _ = frame.shape
    results = model(frame)
    results_sorted = results.pandas().xyxy[0].sort_values('xmax', ascending=0)

    print(f"Resultados de la yolo: {results_sorted}")


    nPiezas = 0
    for i in range(np.size(results_sorted['name'])):
        if (results_sorted['name'][i] == 'Domino-Pieces'):
            nPiezas = nPiezas + 1
    pos_piezas = np.zeros(shape=(nPiezas, 4))
    nP = 0

    array_Agente = np.zeros(shape=(nPiezas, 5))

    puntos_medios, array_Agente = calcular_punto_medio(results_sorted, array_Agente)
    
    array_Agente1 = punto_medio_fichas(array_Agente, nPiezas, results_sorted,zona,width)
    



    imagen_con_lineas, angulos, puntos_medios, array_Agente11 = dibujar_lineas(frame, puntos_medios, array_Agente, nPiezas)
    imagen_con_lineas, angulos, puntos_medios, array_Agente22 = dibujar_lineas(frame, puntos_medios, array_Agente1, nPiezas)

    print (f"Array agente Marcos: {array_Agente11} ")
    print (f"Array agente Alain:  {array_Agente22} ")


def Lectura_Yolo(frame, instruccion,zona):

    global z 
    height, width, _ = frame.shape
    results = model(frame)
    results_sorted = results.pandas().xyxy[0].sort_values('xmax', ascending=0)

    nPiezas = 0
    for i in range(np.size(results_sorted['name'])):
        if (results_sorted['name'][i] == 'Domino-Pieces'):
            nPiezas = nPiezas + 1
    pos_piezas = np.zeros(shape=(nPiezas, 4))
    nP = 0

    array_Agente = np.zeros(shape=(nPiezas, 5))

    puntos_medios, array_Agente = calcular_punto_medio(results_sorted, array_Agente)
    
    array_Agente1 = punto_medio_fichas(array_Agente, nPiezas, results_sorted,zona,width)
    
    print (f"Array agente Marcos: {array_Agente1} ")
    print (f"Array agente Alain:  {array_Agente} ")


    imagen_con_lineas, angulos, puntos_medios, array_Agente = dibujar_lineas(frame, puntos_medios, array_Agente, nPiezas)

    # Creamos estructura de datos para enviar
    comando = instruccion
    robot = comandoVision(comando, nPiezas, array_Agente)
    serialized_data = robot.serialize()
    print(f"Serialized Data: {serialized_data}")

    deserialized_robot = comandoVision.deserialize(serialized_data)
    print(f"Deserialized Data: comando={deserialized_robot.comando}, Npiezas={deserialized_robot.Npiezas}, array={deserialized_robot.array}")

    return serialized_data, nPiezas

#============================================= Manejo de Conexiones ================================================================================

partida = 1
continuar = 0
instruccion = 0

# Creamos un objeto Condition
condicion = threading.Condition()

def recibirInterfaz():
    global partida,continuar,instruccion, condicion

    direccion = direcionesIP.visioninterfaz[0]
    puerto = direcionesIP.visioninterfaz[1]

    rcvInt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rcvInt.bind((direccion, puerto))
    rcvInt.listen(1)
    print("Esperando conexion de la interfaz...\n")

    # Bloquea hasta que recibe una conexion
    clienteRcvInt, direccionRcvInt = rcvInt.accept()
    print("Conexion establecida desde: ", direccionRcvInt,"\n")

    # Bucle para manejar la llegada de mensajes
    while ret:
        mensaje = clienteRcvInt.recv(8).decode()
        
        if (mensaje != ''):
            print("Se ha recibido el mensaje: ", mensaje,"\n")
            if(mensaje == '0'):
                partida = 0
            elif(mensaje == '-1'):
                continuar = 1
            else:
                instruccion = int(mensaje)
            with condicion:
                condicion.notify()

def recibirAgente():
    global partida,continuar,instruccion, condicion

    direccion = direcionesIP.visionAgente[0]
    puerto = direcionesIP.visionAgente[1]
    rcvInt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rcvInt.bind((direccion, puerto))
    rcvInt.listen(1)
    print("Esperando conexion de la interfaz...\n")

    # Bloquea hasta que recibe una conexion
    clienteRcvInt, direccionRcvInt = rcvInt.accept()
    print("Conexion establecida desde: ", direccionRcvInt,"\n")

    # Bucle para manejar la llegada de mensajes
    while ret:
        mensaje = clienteRcvInt.recv(8).decode()
        # print("Se ha recibido el mensaje: ", mensaje,"\n")
        # try:
        #     partida = int(mensaje)
        # except:
        #     print("Mensaje recibido NO VALIDO\n")
        if (mensaje != ''):
            print("Se ha recibido el mensaje: ", mensaje,"\n")
            if(mensaje == '0'):
                partida = 0
            elif(mensaje == '-1'):
                continuar = 1
            else:
                instruccion = int(mensaje)
            with condicion:
                condicion.notify()

    print("Cerrando los sockets")
    clienteRcvInt.close()
    rcvInt.close()

def conectarInterfaz():
    try:
        direccion = direcionesIP.interfaz[0]
        puerto = direcionesIP.interfaz[1]
        envInt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        envInt.connect((direccion, puerto))
        return envInt
    except Exception as e:
        print(f"Error al enviar datos a interfaz de ip {direccion} por socket: {e}")
        return "error"

def conectarAgente():
    try:
        direccion = direcionesIP.agente[0]
        puerto = direcionesIP.agente[1]
        envAg = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        envAg.connect((direccion, puerto))

        return envAg
    except Exception as e:
        print(f"Error al enviar datos agente de ip {direccion} por socket: {e}")
        return "error"

#===================================================== Camara ======================================================================================

def captura_y_procesa_imagenes():
    global frame
    global ret
    cam=0
    while True:
        # Inicializamos la cámara
        print("Iniciando cámara puede tardar un poco.......")
        cap = cv2.VideoCapture(cam)

        if not cap.isOpened():
            print("Error: No se puede abrir la cámara presione una tecla para intentar de nuevo")
            cam = input("Digite un numero del 0 al 10 si quiere cambiar la camara por defecto en otro caso prione cualquier otra tecla")
            
            if 0 >= int(cam) >= 10 :
                cam = 0
        else:
            print("Camara Lista")
            break

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: No se puede recibir frame (stream end?)")
            break
        text= f"Partida: {partida},continuar: {continuar}"
        text1= f"Instruccion: {instruccion}, condicion {condicion}"
        cv2.putText(frame , text, (30,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
        cv2.putText(frame , text1, (30,60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 1)
        
        # Procesamos el frame con el modelo YOLO
        results = model(frame)
        cv2.imshow('YOLO', np.squeeze(results.render()))

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            ret=False
            break
        if key == ord('s'):
            Lectura_YoloP(frame, instruccion)

    # Liberamos la cámara y cerramos todas las ventanas
    cap.release()
    cv2.destroyAllWindows()

print("Iniciando hilo de camaras")
# Crea y lanza el hilo para la captura y procesamiento de imágenes
hilo_captura = threading.Thread(target=captura_y_procesa_imagenes)
hilo_captura.start()

#=================================================== MAIN ==========================================================================================

#Tratar de reconectar
while True:
    # Esperando a la camara
    while True:
        if ret == True:
            break

    envInt = conectarInterfaz()
    if envInt == "error":
        input("Presione cualquier tecla para reconectar...")
    else:
        print("Conexion con interfaz establecida")
        break

thInt = threading.Thread(target=recibirInterfaz)
thInt.daemon = True
thInt.start()
thAg = threading.Thread(target=recibirAgente)
thAg.daemon = True
thAg.start()


print("Esperando señal de la Interfaz...")

while(continuar == 0):
    time.sleep(2.0)
    
print("InterfazConectada")

envAg = conectarAgente()
msgAgente = '1'
#imagenes = obtener_imagenes_en_carpeta(carpeta)


while True:
    if ret == False:
        break

    with condicion:
        print('Dentro del programa...')
        condicion.wait()

        if(instruccion == 3):
            zona = 1
            print("Solicitando al agente que mueva al robot hasta 'Zona Robo'...")
            instr = comandoVision(3,1,np.zeros(shape=(1,5)))
            envAg.send(instr.serialize())

            condicion.wait()
            print("Robot en 'Zona Robo'. Enviando imagen...")
            time.sleep(2.0)

            # PROCESAR IMAGENES Y FORMATEAR EL MENSAJE PARA EL AGENTE
            # SI NO HAY FICHAS DE ROBO, ENVIAR AL AGENTE UN '8'
            data, nPiezas = Lectura_Yolo(frame,instruccion,zona)

            if( nPiezas == 0 ):
                instr = comandoVision(8,1,np.zeros(shape=(1,5)))
                envAg.send(instr.serialize())
                condicion.wait()
                envInt.send('-1'.encode())
            else:
                envAg.send(data)

        if(instruccion == 4):
            zona = 2

            print("Solicitando al agente que mueva al robot hasta 'Zona Fichas'...")
            instr = comandoVision(4,1,np.zeros(shape=(1,5)))
            envAg.send(instr.serialize())

            condicion.wait()
            print("Robot en 'Zona Fichas'. Enviando imagen...")

            # PROCESAR IMAGENES Y FORMATEAR EL MENSAJE PARA EL AGENTE
            data, nPiezas = Lectura_Yolo(frame,instruccion,zona)

            time.sleep(2.0)
            envAg.send(data)

            # ESPERA A QUE EL AGENTE ACTUALICE SUS FICHAS
            condicion.wait()
            # ENVIA CONFIRMACION A INTERFAZ PARA FINALIZAR TURNO
            envInt.send('-1'.encode())


        if(instruccion == 1):
            zona = 0

            print("Solicitando al agente que mueva al robot hasta 'Zona Tablero'...")
            instr = comandoVision(5,1,np.zeros(shape=(1,5)))
            envAg.send(instr.serialize())

            condicion.wait()
            print("Robot en 'Zona Tablero'. Enviando imagen...")

            # PROCESAR IMAGENES Y FORMATEAR EL MENSAJE PARA EL AGENTE
            data, nPiezas = Lectura_Yolo(frame,instruccion,zona)

            time.sleep(2.0)
            envAg.send(data)
            
        

        # Instruccion 7 comienza la secuencia inicial de robo
        if(instruccion == 7):
            zona = 1

            print("Solicitando al agente que mueva al robot a 'Zona Robo'...\n")
            instr = comandoVision(3,1,np.zeros(shape=(1,5)))
            envAg.send(instr.serialize())

            # Espera confirmacion de que el robot está en zona de robo
            condicion.wait()
            print("Robot en 'Zona Robo'. Enviando imagen al agente...\n")

            # PROCESAR IMAGENES Y FORMATEAR EL MENSAJE PARA ENVIAR FICHAS DE ROBO AL AGENTE
            data, nPiezas = Lectura_Yolo(frame,instruccion,zona)
            #data, nPiezas = sim_YOLO(instruccion,zona)

            time.sleep(2.0)
            # CAMBIAR EL '7' POR VUESTRO MENSAJE FORMATEADO CON UN 7 EN EL CAMPO DE INSTRUCCION
            envAg.send(data)

            # ESPERA A QUE EL ROBOT TENGA TODAS SUS FICHAS PARA HACERLE UNA FOTO
            condicion.wait()
            instr = comandoVision(4,1,np.zeros(shape=(1,5)))
            envAg.send(instr.serialize())
            condicion.wait()
            print("Fichas del robot listas. Enviando imagen al agente...\n")
            
            zona = 2
            # PROCESAR IMAGENES Y FORMATEAR EL MENSAJE PARA ENVIAR FICHAS DISPONIBLES AL AGENTE
            # CAMBIAR EL '6' POR VUESTRO MENSAJE FORMATEADO CON UN 6 EN EL CAMPO DE INSTRUCCION
            data, nPiezas = Lectura_Yolo(frame,6,zona)
            #data, nPiezas = sim_YOLO(instruccion,zona)
            envAg.send(data)

            # ESPERA A QUE EL AGENTE LE DIGA EL DOBLE MAS ALTO
            condicion.wait()
            doble = str(instruccion)

            # Devuelve el doble mas alto a la interfaz
            envInt.send(doble.encode())



thInt.join()
thAg.join()
hilo_captura.join()