from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/roadmap')
def roadmap():
    return render_template('roadmap.html')


@app.route('/mining')
def mining():
    return render_template('mining.html')


@app.route('/download')
def download():
    return render_template('download.html')


@app.route('/join')
def join():
    return render_template('join.html')


@app.route('/try')
def tryi():
    return render_template('try.html')


if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')

# test web
# docker run --rm -it --name satorineuron -p 5000:5000 -v c:\repos\Satori\satori:/Satori/satori --env ENV=prod --env WALLETONLYMODE=1 satorinet/satorineuron:latest python /Satori/satori/app.py
