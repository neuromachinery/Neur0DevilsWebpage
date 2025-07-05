from os import path,walk,chdir,link,remove
from flask import Flask, render_template_string, request, render_template,jsonify,send_from_directory
from flask_socketio import SocketIO, emit
from uuid import uuid4
from datetime import datetime
from DBconnect import SocketTransiever
from traceback import format_exc
from threading import Thread
from asyncio import Queue,QueueEmpty
import GifScraper
from time import sleep

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads' 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app)
HOST = "127.0.0.1"
EXT_PORT = 8000
SITE_PORT = 54322
DB_PORT = 54321
MMM_PORT = 54323
ADDRESS_DICT = {
    "DB":(HOST,DB_PORT),
    "MMM":(HOST,MMM_PORT),
    "SITE":(HOST,SITE_PORT)
}
transiever_queue = Queue()

FILE_SIZE_LIMIT = 100*1024*1024
CHAT_LIMIT = 300
SIZE_LIMIT = CHAT_LIMIT*FILE_SIZE_LIMIT
TIMEOUT=0.1 #sec
WAIT_LIMIT = 3 #sec
LogsTable = "LogsSite"
ChatTable = "ChatSite"
FileTable = "FilenamesSite"
MiscTable = "LogsMisc"
DropTable = "dropTable"
DropUsageTable= "dropUsage"
Temp = "Temp"
CWD = path.dirname(path.realpath(__file__))
chdir(CWD)
transiever = SocketTransiever(ADDRESS_DICT["SITE"])
SEND = transiever.send_message
def transiever_queue_get():
    i = 0.0
    while i<WAIT_LIMIT:
        try: return transiever_queue.get_nowait()
        except QueueEmpty:
            sleep(TIMEOUT)
            i+=TIMEOUT
    raise ConnectionError
RECIEVE = transiever_queue_get
def now():
    return datetime.now().strftime("[%d.%m.%Y@%H:%M:%S]")
def countingSort(arr, exp1): 
    n = len(arr) 
    output = [0] * (n) 
    count = [0] * (10) 
    for i in range(0, n): 
        index = (arr[i][1][0]/exp1) 
        count[int((index)%10)] += 1
    for i in range(1,10): 
        count[i] += count[i-1] 
    i = n-1
    while i>=0: 
        index = (arr[i][1][0]/exp1) 
        output[ count[ int((index)%10) ] - 1] = arr[i]
        count[int((index)%10)] -= 1
        i -= 1
    i = 0
    for i in range(0,len(arr)): 
        arr[i] = output[i] 
def radixSort(arr):
    "Directly sorts lists of such structure: list[tuple[str,tuple[int,int]]]"
    max1 = max(arr,key=lambda val:val[1][0])[1][0]
    exp = 1
    while max1 // exp > 0:
        countingSort(arr,exp)
        exp *= 10
def calculateMemeSpace() -> dict[int,tuple[int,int]]:
    "Calculates a dictionary of modification dates of all downloaded media by their paths, plus a total diskspace by 'total'."
    result = {"total":0}
    for dirpath, dirnames, filenames in walk(UPLOAD_FOLDER,followlinks=True):
        for file in filenames:
            file_path = path.join(dirpath, file)
            size = path.getsize(file_path)
            result["total"] += size
            result[file_path] = int(path.getmtime(file_path)),size
    return result

MemeSpace = calculateMemeSpace()

def purge(amount:int): # TODO
    total = MemeSpace["total"]
    target = total - amount
    memes = list(MemeSpace.items())[1:]
    radixSort(memes)
    purge_amount, i = 0,0
    while total - purge_amount > target:
        purge_amount += memes[i][1][1]
        i+=1
    for meme,_size in tuple(memes[:i]):
        remove(meme)
        del MemeSpace[meme]
    MemeSpace["total"] = total - purge_amount
def get_chat_history():
    SEND(ADDRESS_DICT["DB"],sender_name="SITE",target_name="DB",message_type="LST",message=(ChatTable,CHAT_LIMIT,0,True))
    try:data = RECIEVE()["message"][::-1]
    except ConnectionError:
        return jsonify({'error': 'Database unresponsive'}), 500
    return data
@app.route('/')
@app.route('/main.html')
def serve_main_page():
    with open('templates/main.html', 'r', encoding='utf-8') as file:
        html_content = file.read()
    html_content = html_content.replace('RANDOM_GIF', GifScraper.fetch_random_gif())
    return render_template_string(html_content)

@app.route('/chat')
def chat():
    return render_template('chat.html')
@socketio.on('send_message',namespace="/chat")
def handle_send_message(data):
    name = data['name'][:40]
    message = data['message'][:1000]
    channel = data['channel']
    file_id = data['unique_id'] if 'unique_id' in data else None
    external = bool(data['external']) if 'external' in data else False
    if external and file_id:
        unique_id = str(uuid4())
        link(file_id,path.join(app.config['UPLOAD_FOLDER'], unique_id))
        SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="LOG", message=(FileTable, (unique_id, file_id)))
        file_id = unique_id
    ip_address = request.remote_addr
    timestamp = now()  
    log_entry = (name, ip_address, message, timestamp,file_id)
    if not SEND(ADDRESS_DICT["DB"],sender_name="SITE",target_name="DB", message_type="LOG", message=(ChatTable, log_entry)):
        raise ValueError
    emit('receive_message', {'name': name, 'time':timestamp, 'message': message, 'unique_id': file_id, "channel": channel,"external": external}, broadcast=True)
@app.route('/chat_history')
def chat_history():
    messages = get_chat_history()
    try:return jsonify(messages=[{'name': msg[0],'ip':msg[1], 'message': msg[2],'time':msg[3],'unique_id': msg[4]} for msg in messages])
    except IndexError as E:
        print(format_exc(),str(E),messages)
    except TypeError as E:
        ExceptionHandler(E)
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file.content_length > FILE_SIZE_LIMIT:
        return jsonify({'error': f'File size exceeds {FILE_SIZE_LIMIT} MB limit.'}), 400
    if MemeSpace["total"] + file.content_length > SIZE_LIMIT:
        purge(file.content_length)

    unique_id = str(uuid4())
    original_filename = file.filename
    filepath = path.join(app.config['UPLOAD_FOLDER'], unique_id)
    try:file.save(filepath)
    except OSError:
        return jsonify({'error': 'Not enough space on the device'}), 507
    # Log the original filename and its unique ID
    SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="LOG", message=(FileTable, (unique_id, original_filename)))

    return jsonify({'success': True, 'original_filename': original_filename, 'unique_id': unique_id}), 200

@app.route('/download/<unique_id>')
def download_file(unique_id):
    SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="GET", message=(FileTable, "uuid4", unique_id))
    try:
        data = RECIEVE()["message"]
    except ConnectionError:
        return jsonify({'error': 'Database unresponsive'}), 500
    if not data:
        return jsonify({'error': 'File not found'}), 404
    original_filename = data[0][1]
    return send_from_directory(app.config['UPLOAD_FOLDER'], unique_id, as_attachment=True,download_name=original_filename)
@app.route('/make_drop/')
def make_drop():
    return render_template('make_drop.html')
@socketio.on('drop_propose',namespace="/make_drop")
def handle_make_drop(data):
    unique_id=str(uuid4())
    SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="LOG", message=(DropTable, (unique_id,data["drop_data"],data["usage_count"])))
    emit('drop_confirmed',{"unique_id":unique_id},namespace="/make_drop")
@app.route('/get_drop/<unique_id>')
def get_drop(unique_id):
    try:
        SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="GET", message=(DropTable, "UUID", unique_id))
        data = RECIEVE()["message"]
        if not data:
            return jsonify({'error': 'Drop not found'}), 404
        SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="CNT", message=(DropUsageTable, "UUID", unique_id))
        used = RECIEVE()["message"]
        _,drop,uses = data[0]
    except ConnectionError:
        return jsonify({'error': 'Database unresponsive'}), 500
    if used<uses:
        log_entry = (unique_id,now(),request.remote_addr)
        SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="LOG", message=(DropUsageTable, log_entry))
        return render_template('drop.html',drop_data=drop,uses=uses-used-1)
    return render_template("drop_exhausted.html",max_usage=uses)
@app.route('/about')
def about():
    return render_template('about.html')

@app.after_request
def log_request(response):
    message = (
        request.remote_addr,
        response.status_code,
        request.method + ' ' + request.path,
        now(),
    )
    SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="LOG", message=(LogsTable, message))
    return response
def ExceptionHandler(exception:Exception,*args):
    exception_formatted = f"{exception}; {format_exc()}; {type(exception)}; args:{args}"
    print(exception_formatted)
    date = now()
    SEND(
        ADDRESS_DICT["DB"],
        sender_name="SITE",
        target_name="DB", 
        message_type="LOG",
        message=(MiscTable,(exception_formatted,date))
    )

class NetPort():
    def __init__(self) -> None:
        self.thread = Thread(target=self.main,daemon=True)
    def process(self,conn,addr):
        try:
            while not conn._closed:
                data = transiever.receive_message(conn)
                if not data: break
                if data["name"] == "DB":
                    transiever_queue.put_nowait(data)
                    return
                if data["name"] == "MMM" and data["type"] == "GET":
                    response = {"CWD":CWD,"UPLOADS":UPLOAD_FOLDER,"CWD+UPLOADS":path.join(CWD,UPLOAD_FOLDER)}[data["message"]]
                    transiever.send_message(ADDRESS_DICT["MMM"],"SITE","MMM","RES",response)
        except OSError:pass
        except Exception as E:
            ExceptionHandler(E)
        finally:
            if not conn._closed:conn.close()
    def main(self):
        transiever = SocketTransiever((HOST,SITE_PORT))
        while True:
            Thread(target=self.process,args=transiever.accept(),daemon=True).start()

    def run(self):
        try:self.thread.start()
        except Exception as E:
            ExceptionHandler(E)
if __name__ == "__main__":
    work=True
    while work:
        try:
            @socketio.on_error()
            def error_handler(E):
                ExceptionHandler(E)
            @socketio.on('disconnect')
            def handle_disconnect():pass
            NetPort().run()
            socketio.run(app,host="0.0.0.0", port=EXT_PORT, debug=False,allow_unsafe_werkzeug=True)
            quit()
            
        except KeyboardInterrupt as E:
            ExceptionHandler(E)
            socketio.stop()
            work=False
        except Exception as E:
            ExceptionHandler(E)
            socketio.stop()