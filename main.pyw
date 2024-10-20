import os
import http.server
import socketserver
from DBconnect import SocketSender
from routing import HOSTS
import shutil
from time import time
from urllib.parse import quote, unquote
import GifScraper

PORT = 8000
SHARED_FOLDER = "Shared"  # Change this to your Shared folder path
SIZE_LIMIT_MB = 100  # Set a size limit for notifications (e.g., 100 MB)
Table = "LogsSite"
sender = SocketSender(HOSTS["SITE"])
sender.connect()
SEND = sender.send_message

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        message = (
            self.address_string(),
            int(code),
            self.requestline.translate(self._control_char_table),
            int(time()),
        )
        SEND("SITE","LOG",(Table,message))
    def do_GET(self):
        if self.path == '/':
            self.serve_main_page()
        elif self.path == '/main.html':
            self.serve_main_page()
        elif self.path.startswith('/download/'):
            self.handle_download()
        else:
            super().do_GET()
    def server_hello_page(self):
        # Read the existing main.html file
        with open('It works!.htm', 'r', encoding='utf-8') as file:
            html_content = file.read()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    def server_about_page(self):
        # Read the existing main.html file
        with open('about.html', 'r', encoding='utf-8') as file:
            html_content = file.read()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    def serve_main_page(self):
        # Read the existing main.html file
        with open('main.html', 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Generate file and folder links for the Shared folder
        items = os.listdir(SHARED_FOLDER)
        item_links = ''.join(
            self.create_link(item) for item in items if os.path.exists(os.path.join(SHARED_FOLDER, item))
        )

        # Insert dynamic links into the HTML content
        html_content = html_content.replace('<!-- FILE_LINKS -->', item_links)
        html_content = html_content.replace('RANDOM_GIF', GifScraper.fetch_random_gif())
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

    def create_link(self, item):
        item_path = os.path.join(SHARED_FOLDER, item)
        size_warning = ""
        
        # Check size and prepare warning if necessary
        if os.path.isdir(item_path):
            folder_size = self.get_folder_size(item_path)
            if folder_size > SIZE_LIMIT_MB * 1024 * 1024:  # Convert MB to bytes
                size_warning = f'<span style="color: red;">(Large folder: {folder_size / (1024 * 1024):.2f} MB)</span>'
        elif os.path.isfile(item_path):
            file_size = os.path.getsize(item_path)
            if file_size > SIZE_LIMIT_MB * 1024 * 1024:  # Convert MB to bytes
                size_warning = f'<span style="color: red;">(Large file: {file_size / (1024 * 1024):.2f} MB)</span>'
        
        # Add onClick event to show loading popup
        return f'<li><a href="/download/{quote(item)}" onclick="showLoadingPopup()">{item}</a> {size_warning}</li>'

    def get_folder_size(self, folder):
        """Calculate the total size of all files in a folder."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size

    def handle_download(self):
        item_name = unquote(self.path.split('/')[-1])  # Decode the URL component
        item_path = os.path.join(SHARED_FOLDER, item_name)

        if os.path.isdir(item_path):
            # Create a zip file of the directory
            shutil.make_archive(item_name, 'zip', item_path)
            zip_file_path = f"{item_name}.zip"
            self.send_file(zip_file_path)
            os.remove(zip_file_path)  # Clean up after sending
        elif os.path.isfile(item_path):
            self.send_file(item_path)
        else:
            self.send_error(404, "File or directory not found.")

    def send_file(self, path):
        """Send a file to the client."""
        self.send_response(200)
        
        # Encode filename for Content-Disposition
        filename = os.path.basename(path)
        self.send_header('Content-Disposition', f'attachment; filename*=UTF-8\'\'{quote(filename)}')
        
        self.send_header('Content-type', 'application/octet-stream')
        self.end_headers()
        
        with open(path, 'rb') as file:
            self.wfile.write(file.read())

with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
    #print(f"Serving at port {PORT}")
    try:httpd.serve_forever()
    except KeyboardInterrupt:quit()
