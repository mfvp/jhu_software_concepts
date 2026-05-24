# run.py
# This is the starting point of the web application.
# To launch the site, open a terminal and type: python run.py

# We import the create_app function from our app package (the app/ folder).
# create_app() builds and configures the Flask application for us.
from app import create_app

# Call create_app() to get our Flask application object ready to use.
app = create_app()

# This block only runs when we execute this file directly (not when it is
# imported by another module). It is a common Python pattern.
if __name__ == '__main__':
    # app.run() starts the web server.
    #   host='0.0.0.0'  means the server listens on all network interfaces,
    #                   so it can be reached at http://localhost:8080
    #   port=8080       sets the port number (the default Flask port is 5000,
    #                   but the assignment requires 8080)
    #   debug=True      automatically restarts the server when we save changes
    #                   and shows helpful error messages in the browser
    app.run(host='0.0.0.0', port=8080, debug=True)
