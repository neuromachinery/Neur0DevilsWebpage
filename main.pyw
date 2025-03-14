from os import mkdir,path,listdir,walk,makedirs,chdir,link
from shutil import rmtree,make_archive
from flask import Flask, send_file, render_template_string, request, abort, render_template,jsonify,send_from_directory
from flask_socketio import SocketIO, emit
from uuid import uuid4
from urllib.parse import quote, unquote
from datetime import datetime
from DBconnect import SocketTransiever
from traceback import format_exc
from threading import Thread
from asyncio import Queue,QueueEmpty
import GifScraper
from time import sleep

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'  # Define where to save uploaded files
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

SHARED_FOLDER = "Shared"  # Change this to your Shared folder path
SIZE_LIMIT_MB = 100  # Set a size limit (e.g., 100 MB)
CHAT_LIMIT = 150
TIMEOUT=0.1 #sec
WAIT_LIMIT = 3 #sec
LogsTable = "LogsSite"
ChatTable = "ChatSite"
FileTable = "FilenamesSite"
MiscTable = "LogsMisc"
DropTable = "DROPTABLE"
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
def clean_uploads_folder():
    """
    Удаляет все файлы в папке, если общий размер файлов превышает заданное значение.

    :param folder_path: Путь к папке с загруженными файлами (по умолчанию 'uploads').
    :param max_size_mb: Максимальный размер в мегабайтах, после которого файлы будут удалены.
    """
    # Конвертируем максимальный размер в байты

    # Проверяем, существует ли папка
    if not path.exists(UPLOAD_FOLDER):
        print(f"'{UPLOAD_FOLDER}' not found, creating... ",end="")
        try:mkdir(UPLOAD_FOLDER)
        except Exception as E:
            print(format_exc(),str(E))
            quit()
        else:
            print("created.")
            return

    # Рассчитываем общий размер файлов в папке
    total_size = 0
    for dirpath, dirnames, filenames in walk(UPLOAD_FOLDER,followlinks=True):
        for file in filenames:
            file_path = path.join(dirpath, file)
            total_size += path.getsize(file_path)

    print(f"'{UPLOAD_FOLDER}' total size: {total_size / (1024 * 1024):.2f} MB")

    # Если общий размер превышает заданный лимит, удаляем все файлы
    if total_size > SIZE_LIMIT_MB*1024*1024:
        rmtree(UPLOAD_FOLDER)  # Удаляем папку и все её содержимое
        makedirs(UPLOAD_FOLDER)     # Восстанавливаем пустую папку
        print(f"'{UPLOAD_FOLDER}' was purged.")
    else:
        print("Size is acceptable. No cleaning required")
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

    items = listdir(SHARED_FOLDER)
    item_links = ''.join(
        create_link(item) for item in items if path.exists(path.join(SHARED_FOLDER, item))
    )

    html_content = html_content.replace('<!-- FILE_LINKS -->', item_links)
    html_content = html_content.replace('RANDOM_GIF', GifScraper.fetch_random_gif())
    
    return render_template_string(html_content)

@app.route('/chat')
def chat():
    return render_template('chat.html')
@socketio.on('send_message')
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
    ip_address = request.remote_addr # Получаем IP-адрес клиента
    timestamp = now()  # Получаем текущее время
    log_entry = (name, ip_address, message, timestamp,file_id)
    # Отправляем сообщение через SEND
    SEND(ADDRESS_DICT["DB"],sender_name="SITE",target_name="DB", message_type="LOG", message=(ChatTable, log_entry))    
    # Рассылаем сообщение всем подключенным клиентам
    emit('receive_message', {'name': name, 'time':timestamp, 'message': message, 'unique_id': file_id, "channel": channel,"external": external}, broadcast=True)
@app.route('/chat_history')
def chat_history():
    messages = get_chat_history()  # Получаем историю сообщений
    try:return jsonify(messages=[{'name': msg[0],'ip':msg[1], 'message': msg[2],'time':msg[3],'unique_id': msg[4]} for msg in messages])
    except IndexError as E:
        print(format_exc(),str(E),messages)
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file.content_length > SIZE_LIMIT_MB * 1024 * 1024:
        return jsonify({'error': f'File size exceeds {SIZE_LIMIT_MB} MB limit.'}), 400
    # Generate a unique identifier for the file
    unique_id = str(uuid4())
    
    # Save the file with the unique identifier but keep the original filename
    original_filename = file.filename
    filepath = path.join(app.config['UPLOAD_FOLDER'], unique_id)
    
    # Save the file with the unique ID as its name
    try:file.save(filepath)
    except OSError:
        return jsonify({'error': 'Not enough space on the device'}), 507
    # Log the original filename and its unique ID
    SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="LOG", message=(FileTable, (unique_id, original_filename)))

    return jsonify({'success': True, 'original_filename': original_filename, 'unique_id': unique_id}), 200

@app.route('/download/<unique_id>')
def download_file(unique_id):
    #print(f"{unique_id} -> ",end="")
    SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="GET", message=(FileTable, "uuid4", unique_id))
    try:
        data = RECIEVE()["message"]
    except ConnectionError:
        return jsonify({'error': 'Database unresponsive'}), 500
    sleep(0.17)
    if not data:
        return jsonify({'error': 'File not found'}), 404
    #print(data[0][1])
    original_filename = data[0][1]
    return send_from_directory(app.config['UPLOAD_FOLDER'], unique_id, as_attachment=True,download_name=original_filename)
@app.route('/make_drop')
def make_drop():
    str(uuid4())
    return render_template('make_drop.html')
@app.route('/get_drop/<unique_id>')
def get_drop(unique_id):
    #print(f"{unique_id} -> ",end="")
    SEND(ADDRESS_DICT["DB"],sender_name="SITE", target_name="DB",message_type="GET", message=(DropTable, "UUID", unique_id))
    try:
        data = RECIEVE()["message"]
    except ConnectionError:
        return jsonify({'error': 'Database unresponsive'}), 500
    sleep(0.17)
    if not data:
        return jsonify({'error': 'Drop not found'}), 404
    if not data[0][-1]: #not already used
        drop = data[0][1]
        return render_template('drop.html',drop_data=drop)
    return jsonify({'error': 'Drop has expired after 1 use'}), 403
@app.route('/about')
def about():
    return render_template('about.html')
def create_link(item):
    item_path = path.join(SHARED_FOLDER, item)
    size_warning = ""
    
    if path.isdir(item_path):
        folder_size = get_folder_size(item_path)
        if folder_size > SIZE_LIMIT_MB * 1024 * 1024:
            size_warning = f'<span style="color: red;">(Large folder: {folder_size / (1024 * 1024):.2f} MB)</span>'
    elif path.isfile(item_path):
        file_size = path.getsize(item_path)
        if file_size > SIZE_LIMIT_MB * 1024 * 1024:
            size_warning = f'<span style="color: red;">(Large file: {file_size / (1024 * 1024):.2f} MB)</span>'
    
    return f'<li><a href="/download/{quote(item)}" onclick="showLoadingPopup()">{item}</a> {size_warning}</li>'

def get_folder_size(folder):
    total_size = 0
    for dirpath, dirnames, filenames in walk(folder):
        for f in filenames:
            fp = path.join(dirpath, f)
            total_size += path.getsize(fp)
    return total_size

@app.route('/download/<path:item_name>')
def handle_download(item_name):
    item_path = path.join(SHARED_FOLDER, unquote(item_name))

    if path.isdir(item_path):
        zip_file_path = make_archive(f"{Temp}/{item_name}", 'zip', item_path)
        return send_file(zip_file_path, as_attachment=True)
    elif path.isfile(item_path):
        return send_file(item_path, as_attachment=True)
    
    abort(404)

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
def ExceptionHandler(exception:Exception):
    exception_formatted = f"{exception}; {format_exc()}; {type(exception)}"
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
    clean_uploads_folder()
    while True:
        try:
            @socketio.on_error()
            def error_handler(E):
                ExceptionHandler(E)
            @socketio.on('disconnect')
            def handle_disconnect():pass
            NetPort().run()
            socketio.run(app,host="0.0.0.0", port=EXT_PORT, debug=False)
        except KeyboardInterrupt:quit()
        except Exception as E:
            ExceptionHandler(E)