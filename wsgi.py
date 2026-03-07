from Neur0DevilWebsite import app, socketio,ExceptionHandler,EXT_PORT,CERT_KEY,CERTIFICATE,NetPort  # import your app and socketio

def create_app():
    # Wire handlers once
    @socketio.on_error()
    def error_handler(E):
        ExceptionHandler(E)

    @socketio.on('disconnect')
    def handle_disconnect():
        pass

    return app

# For Gunicorn + Eventlet
if __name__ == "__main__":
    # Only for local dev
    socketio.run(
        create_app(),
        host="::",
        port=EXT_PORT,
        certfile=CERTIFICATE,
        keyfile=CERT_KEY,
        debug=False,
    )
else:
    # For Gunicorn entry point
    create_app()

# Background thread
NetPort().run()
