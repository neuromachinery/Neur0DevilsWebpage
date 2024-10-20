import os
import shutil
from routing import HOSTS 
from flask import Flask, send_file, render_template_string, request, abort, render_template,jsonify
from urllib.parse import quote, unquote
from time import time
from DBconnect import SocketTransiever
import GifScraper

app = Flask(__name__)
PORT = 8000
SHARED_FOLDER = "Shared"  # Change this to your Shared folder path
SIZE_LIMIT_MB = 100  # Set a size limit for notifications (e.g., 100 MB)
LogsTable = "LogsSite"
ChatTable = "ChatSite"
Temp = "Temp"
transiever = SocketTransiever(target=HOSTS["SITE"])
transiever.connect()
SEND = transiever.send_message
RECIEVE = transiever.receive_message
def get_chat_history():
    SEND(sender_name="SITE",message_type="LST",message=(ChatTable,50))
    data = RECIEVE()["message"]
    return data
@app.route('/')
@app.route('/main.html')
def serve_main_page():
    with open('templates/main.html', 'r', encoding='utf-8') as file:
        html_content = file.read()

    items = os.listdir(SHARED_FOLDER)
    item_links = ''.join(
        create_link(item) for item in items if os.path.exists(os.path.join(SHARED_FOLDER, item))
    )

    html_content = html_content.replace('<!-- FILE_LINKS -->', item_links)
    html_content = html_content.replace('RANDOM_GIF', GifScraper.fetch_random_gif())
    
    return render_template_string(html_content)

@app.route('/chat')
def chat():
    return render_template('chat.html')
@app.route('/send_chat_message', methods=['POST'])
def send_chat_message():
    data = request.get_json()
    name = data.get('name')
    message = data.get('message')
    ip_address = request.remote_addr
    timestamp = int(time())

    # Формируем кортеж для записи в базу данных
    log_entry = (name, ip_address, message, timestamp)

    # Отправляем сообщение через SEND
    SEND(sender_name="SITE", message_type="LOG", message=(ChatTable, log_entry))

    return jsonify(success=True)
@app.route('/chat_history')
def chat_history():
    messages = get_chat_history()  # Получаем историю сообщений
    return jsonify(messages=[{'name': msg[0], 'message': msg[2]} for msg in messages])
@app.route('/about')
def about():
    return render_template('about.html')
def create_link(item):
    item_path = os.path.join(SHARED_FOLDER, item)
    size_warning = ""
    
    if os.path.isdir(item_path):
        folder_size = get_folder_size(item_path)
        if folder_size > SIZE_LIMIT_MB * 1024 * 1024:
            size_warning = f'<span style="color: red;">(Large folder: {folder_size / (1024 * 1024):.2f} MB)</span>'
    elif os.path.isfile(item_path):
        file_size = os.path.getsize(item_path)
        if file_size > SIZE_LIMIT_MB * 1024 * 1024:
            size_warning = f'<span style="color: red;">(Large file: {file_size / (1024 * 1024):.2f} MB)</span>'
    
    return f'<li><a href="/download/{quote(item)}" onclick="showLoadingPopup()">{item}</a> {size_warning}</li>'

def get_folder_size(folder):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

@app.route('/download/<path:item_name>')
def handle_download(item_name):
    item_path = os.path.join(SHARED_FOLDER, unquote(item_name))

    if os.path.isdir(item_path):
        zip_file_path = shutil.make_archive(f"{Temp}/{item_name}", 'zip', item_path)
        return send_file(zip_file_path, as_attachment=True)
    elif os.path.isfile(item_path):
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
    
    app.run(host="0.0.0.0", port=PORT, debug=False)
