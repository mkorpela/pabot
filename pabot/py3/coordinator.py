from flask import Flask, request
import json

app = Flask(__name__)

@app.route("/")
def hello():
    print(f"moi {1}")
    return "Hello, World!"

@app.route("/workers")
def workers():
    return {
        'workers': [1,2,3]
    }

@app.route("/workers", methods=["POST"])
def create_worker():
    return {
        'isitok': True
    }

def main(args=None):
    app.run(host='0.0.0.0', port='8000', debug=True)


if __name__ == '__main__':
    main()