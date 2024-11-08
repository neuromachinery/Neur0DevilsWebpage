from os import mkdir,path,listdir,walk,makedirs
from shutil import rmtree,make_archive
from dotenv import load_dotenv, dotenv_values
from sys import argv
from flask import Flask, send_file, render_template_string, request, abort, render_template,jsonify,send_from_directory
from flask_socketio import SocketIO, emit
from uuid import uuid4
from urllib.parse import quote, unquote
from time import time
from datetime import datetime
from DBconnect import SocketTransiever
import GifScraper

from time import sleep

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'  # Define where to save uploaded files
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app)
PORT = 8000
SHARED_FOLDER = "Shared"  # Change this to your Shared folder path
SIZE_LIMIT_MB = 100  # Set a size limit (e.g., 100 MB)
CHAT_LIMIT = 150
LogsTable = "LogsSite"
ChatTable = "ChatSite"
FileTable = "FilenamesSite"
MiscTable = "LogsMisc"
Temp = "Temp"
HOST = "127.0.0.1"

if len(argv)>1:
    env = argv[1] 
else: 
    env = path.join(path.dirname(path.realpath(__file__)),".env")
load_dotenv(env)
config = dotenv_values(env)
try:
    transiever = SocketTransiever(target=(HOST,int(config["SITE"])))
except KeyError:
    print(f"Absence or corruption of .env file '{env}'")
    quit()
SEND = transiever.send_message
RECIEVE = transiever.receive_message
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
            print(E,str(E))
            quit()
        else:
            print("created.")
            return

    # Рассчитываем общий размер файлов в папке
    total_size = 0
    for dirpath, dirnames, filenames in walk(UPLOAD_FOLDER):
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
    SEND(sender_name="SITE",message_type="LST",message=(ChatTable,CHAT_LIMIT,0,True))
    data = RECIEVE()["message"][::-1]
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
    name = data['name']
    message = data['message']
    unique_id = data['unique_id'] if 'unique_id' in data else None
    ip_address = request.remote_addr  # Получаем IP-адрес клиента
    timestamp = int(time())  # Получаем текущее время в секундах
    log_entry = (name, ip_address, message, timestamp,unique_id)
    # Отправляем сообщение через SEND
    SEND(sender_name="SITE", message_type="LOG", message=(ChatTable, log_entry))    
    # Рассылаем сообщение всем подключенным клиентам
    emit('receive_message', {'name': name, 'message': message, 'unique_id': unique_id}, broadcast=True)
@app.route('/chat_history')
def chat_history():
    messages = get_chat_history()  # Получаем историю сообщений
    try:return jsonify(messages=[{'name': msg[0], 'message': msg[2],'unique_id': msg[4]} for msg in messages])
    except IndexError as E:
        print(E,str(E),messages)
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
    SEND(sender_name="SITE", message_type="LOG", message=(FileTable, (unique_id, original_filename)))

    return jsonify({'success': True, 'original_filename': original_filename, 'unique_id': unique_id}), 200

@app.route('/download/<unique_id>')
def download_file(unique_id):
    print(f"{unique_id} -> ",end="")
    SEND(sender_name="SITE", message_type="GET", message=(FileTable, "uuid4", unique_id))
    data = RECIEVE()["message"]
    sleep(0.17)
    if not data:
        return jsonify({'error': 'File not found'}), 404
    print(data[0][1])
    original_filename = data[0][1]
    return send_from_directory(app.config['UPLOAD_FOLDER'], unique_id, as_attachment=True,download_name=original_filename)
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
        int(time()),
    )
    SEND(sender_name="SITE", message_type="LOG", message=(LogsTable, message))
    return response

if __name__ == "__main__":
    clean_uploads_folder()
    try:transiever.connect()
    except KeyboardInterrupt:
        quit()
    while True:
        try:
            @socketio.on_error()
            def error_handler(E):
                SEND(sender_name="SITE", message_type="LOG",message=(MiscTable,(str(E),datetime.now().strftime("[%d.%m.%Y@%H:%M:%S]"))))
            @socketio.on('disconnect')
            def handle_disconnect():
                SEND(sender_name="SITE", message_type="LOG",message=(MiscTable,("disconnect",datetime.now().strftime("[%d.%m.%Y@%H:%M:%S]"))))
            socketio.run(app,host="0.0.0.0", port=PORT, debug=False)
        except KeyboardInterrupt:quit()
        except Exception as E:
            SEND(sender_name="SITE", message_type="LOG",message=(MiscTable,(str(E),datetime.now().strftime("[%d.%m.%Y@%H:%M:%S]"))))