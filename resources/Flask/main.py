try:
    import time
    import csv
    import threading
    from gevent.pywsgi import WSGIServer
    from jsonObject import jsonObject
    from ArduinoConnection import ArduinoConnection
    from flask import Flask, Response, stream_with_context, request, render_template, redirect, url_for
    from datetime import datetime
    from gevent import monkey
    monkey.patch_all()
except Exception as eImp:
    print(f"Ocurrió el error de importación: {eImp}")

# Inits arduino connection
conn = ArduinoConnection()
conn.startCommunication()

# Variables for reading operation mode
sem = threading.Semaphore()
firstTime = True
modo = ""
lightMode = ""

# Keeps the data received from the arduino´s stream
streamData = []

# JSON read
jsonMain = jsonObject()

# Creation of the flask app.
app = Flask(__name__)
app.secret_key = "clave_secreta_flask"


@app.context_processor  # Context processor
def date_now():
    return {
        'now': datetime.utcnow()
    }

#---------------------------------Endpoints------------------------------------#


def firstTimeLoad():
    global jsonMain, modo, lightMode, rangoResAgua, rangoTerrario, rangoHum, correoGDCode, nomL, nomApp, versionApp, descripcionApp

    jsonMain.readData()
    modo = jsonMain.jsonData['configuracion']['modo']
    lightMode = jsonMain.jsonData['configuracion']['dia-noche']
    rangoResAgua = jsonMain.jsonData['configuracion']['temperaturas-rangos']['rangoResAgua']
    rangoTerrario = jsonMain.jsonData['configuracion']['temperaturas-rangos']['rangoTempDHT']
    rangoHum = jsonMain.jsonData['configuracion']['humedad-rango']['rangoHumedad']
    correoGDCode = jsonMain.jsonData['correo']
    nomL = jsonMain.jsonData['usuario']['usuario-nl']
    nomApp = jsonMain.jsonData['nombre-app']
    versionApp = jsonMain.jsonData['version']
    descripcionApp = jsonMain.jsonData['descripcion-app']

    number = 1 if modo == "true" or modo == 1 else 0
    text = "auto{}".format(str(number))
    sem.acquire()
    _ = conn.communication(text)
    sem.release()

    number = 1 if lightMode == "true" or lightMode == 1 else 0
    text = "lght{}".format(str(number))
    sem.acquire()
    _ = conn.communication(text)
    sem.release()


@app.route('/')  # Initial route of the project.
def index():
    global firstTime, nomL, nomApp

    if firstTime:
        firstTimeLoad()
        firstTime = False
        return render_template('bienvenida.html', pushed=modo, lightmode=lightMode, offButton=1, dis="hidden", nl=nomL, nomRealApp=nomApp)

    if modo == 'true' or modo == 1:
        return render_template('automatico.html', autoLightMode="disabled", autoLight="disabled")
    if modo == 'false' or modo == 0:
        return render_template('manual.html')


@app.route("/listen")
def listen():

    def respond_to_client():
        global streamData
        while True:
            sem.acquire()
            succes = conn.communication("strm")
            sem.release()
            # print(conn.receivedData)
            if not succes:
                pass
            reader = csv.reader(conn.receivedData.splitlines())
            streamData = list(reader)
            # print(streamData)
            yield f"id: 1\ndata: {conn.receivedData}\nevent: online\n\n"
            # DO NOT QUIT: This time sleep is for initialize the electron.
            time.sleep(5)
    return Response(respond_to_client(), mimetype='text/event-stream')


@app.route('/indexevents', methods=["POST"])
def indexEvents():
    global modo, lightMode

    if request.method == "POST" and "modoOperacion" in request.form:
        receivedMode = request.form.get("modoOperacion")
        if receivedMode != modo:
            modo = receivedMode
            jsonMain.readData()
            jsonMain.writeData_changeMode(modo)
            number = 1 if modo == "true" or modo == 1 else 0
            text = "auto{}".format(str(number))
            sem.acquire()
            succes = conn.communication(text)
            if not succes:
                return "error"
            sem.release()
        return "mode changed"

    if request.method == "POST" and "lighMode" in request.form:
        receivedMode = request.form.get("lighMode")
        if receivedMode != lightMode:
            lightMode = receivedMode
            jsonMain.readData()
            jsonMain.writeData_changeLightMode(lightMode)
            number = 1 if lightMode == "true" or lightMode == 1 else 0
            text = "lght{}".format(str(number))
            sem.acquire()
            succes = conn.communication(text)
            if not succes:
                return "error"
            sem.release()
        return "light mode changed"

    if request.method == "POST" and "lightStatus" in request.form:
        onoffLight = request.form.get("lightStatus")
        if onoffLight:
            text = "bulb"
            sem.acquire()
            succes = conn.communication(text)
            if not succes:
                return "error"
            sem.release()
            return "changeLight"

    if request.method == "POST" and "rellenar" in request.form:
        rellenar = request.form.get("rellenar")
        if rellenar:
            text = "bwtr{}".format(str(rellenar))
            sem.acquire()
            succes = conn.communication(text)
            if not succes:
                return "error"
            sem.release()
        return "rellenando"

    if request.method == "POST" and "humedecer" in request.form:
        hmd = request.form.get("humedecer")
        if hmd:
            text = "hmdf"
            sem.acquire()
            succes = conn.communication(text)
            if not succes:
                return "error"
            sem.release()
        return "humedecido"

    return "error"


@app.route('/configuracion', methods=["POST", "GET"])
def configuracion():
    global rangoResAgua, rangoTerrario, rangoHum

    if request.method == "POST":
        TempAgua = request.form['TempAguaReserva']
        TempTerra = request.form['TempTerrario']
        Hum = request.form['Humedad']
        if rangoResAgua != TempAgua:
            rangoResAgua = TempAgua
            jsonMain.readData()
            jsonMain.writeData_changeRanges(TempAgua, 0)

        elif rangoTerrario != TempTerra:
            rangoTerrario = TempTerra
            jsonMain.readData()
            jsonMain.writeData_changeRanges(TempTerra, 1)

        elif rangoHum != Hum:
            rangoHum = Hum
            jsonMain.readData()
            jsonMain.writeData_changeRanges(Hum, 2)
        # Validar que si los campos se quedan vacíos entonces mande el valor que ya está en configuración desde el principio.
        # Mandar también las variables al arduino y de igual manera actualizar el archivo json con los nuevos valores.
        return render_template('configuracion.html', rango1=f"{TempAgua}", rango2=f"{TempTerra}", rango3=f"{Hum}")
    return render_template('configuracion.html', rango1=f"{rangoResAgua}", rango2=f"{rangoTerrario}", rango3=f"{rangoHum}")


@app.route('/contacto')
def contacto():
    global correoGDCode, nomApp, versionApp, descripcionApp

    return render_template('contacto.html', correo=correoGDCode, nombreApp=nomApp, versionDeApp=versionApp, decApp=descripcionApp)


@app.route('/help')
def help():
    return render_template('ManUsu.html', status="hidden")


@app.route('/closeApp', methods=['POST'])
def closeAll():
    msg = request.form.get("closeMsg")
    if msg == "closeAll":
        conn.closeConnection()
    return "closed"

#----------------------------Error Handlers------------------------------------#


@app.route("/error500")
def error():
    return render_template('errorHandlers/error500.html')


#-------------------------------Execute----------------------------------------#

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
