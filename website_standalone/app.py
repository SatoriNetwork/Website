#!/usr/bin/env python
# -*- coding: utf-8 -*-

# run with:
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &

'''
The Satori Website. Needs connection to the database.
'''

from typing import Union
import os
import json
import secrets
import datetime as dt
from waitress import serve
from flask import Flask, Response, render_template, jsonify, request, redirect
# from satoricentral import logging
'''early access doesn't save to the database, it just saves to a text file.'''


class EarlyAccess():
    def __init__(self, email: str = ''):
        self.email = email

    def save(self):
        with open('/Satori/Central/database/log/earlyAccess.txt', 'a') as f:
            f.write(self.email + '\n')


###############################################################################
## Globals ####################################################################
###############################################################################

debug = True
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
DEVMODE = os.getenv('DEVMODE') == 'True'

###############################################################################
## Helpers ####################################################################
###############################################################################


def context(title: str = 'Satori', **kwargs):
    return {'title': title, **kwargs}


###############################################################################
## Functions ##################################################################
###############################################################################


@app.before_request
def before_request():
    if not DEVMODE:
        url = request.url
        code = 200
        if url.startswith('http://127.0.0.1'):
            return
        for unsecure in ['http://www.', 'www.', 'http://']:
            if url.startswith(unsecure):
                url = url.replace(unsecure, 'https://', 1)
                code = 301
        for empty in ['satorinet.io', 'test.satorinet.io']:
            if url.startswith(empty):
                url = f'https://{url}'
                code = 301
        if code == 301:
            return redirect(url, code=code)

###############################################################################
## Errors #####################################################################
###############################################################################


@app.errorhandler(404)
def not_found(e):
    return '404', 404

###############################################################################
## Routes - static ############################################################
###############################################################################


# @app.route('/kwargs')
# def kwargs():
#    '''
#    ...com/kwargs?0-name=widget_name0&0-value=widget_value0&0-type=widget_type0&
#    1-name=widget_name1&1-value=widget_value1&1-#type=widget_type1
#    '''
#    kwargs = {}
#    for i in range(25):
#        if request.args.get(f'{i}-name') and request.args.get(f'{i}-value'):
#            kwargs[request.args.get(f'{i}-name')
#                   ] = request.args.get(f'{i}-value')
#            kwargs[request.args.get(f'{i}-name') +
#                   '-type'] = request.args.get(f'{i}-type')
#    return jsonify(kwargs)

###############################################################################
## Routes - Events ############################################################
###############################################################################


###############################################################################
## Routes - Browser ###########################################################
###############################################################################


# for testing
# @app.route('/admin', methods=['GET'])
# def admin(term=None):
#  try:
#  SatoriPubSubConn()
#  return generateAdminKey(), 200
#  except Exception as e:
#  return str(e), 400


@app.route('/', methods=['GET'])
@app.route('/home', methods=['GET'])
@app.route('/search/<term>', methods=['GET'])
def search(term=None):
    ''' searching for a stream '''
    try:
        return render_template(
            'home.html',
            **context(show='search'))
    except Exception as e:
        return str(e), 400

# form to make drop down for stream selection


@app.route('/vision', methods=['GET'])
def vision():
    ''' static data '''
    return render_template('home.html', **context(show='vision'))


@app.route('/roadmap', methods=['GET'])
def roadmap():
    ''' static data '''
    return render_template('home.html', **context(show='roadmap'))


@app.route('/team', methods=['GET'])
def team():
    ''' static data '''
    return render_template('home.html', **context(show='team'))


@app.route('/join', methods=['GET'])
def join():
    ''' static data '''
    return render_template('home.html', **context(show='join'))


@app.route('/download', methods=['GET'])
def download():
    ''' static data '''
    return render_template('home.html', **context(show='download'))


@app.route('/download/<ref>', methods=['GET'])
def downloadWithReferal(ref: str):
    ''' static data '''
    return render_template('home.html', **context(show='download'))


@app.route('/tokenomics', methods=['GET'])
def tokenomics():
    ''' static data '''
    # don't include it here because we just call it from js everytime anyway.
    # try:
    #    allocation = MintManifest.allocation()
    # except Exception as _:
    #    allocation = {
    #        'predictors': 0.5,
    #        'oracles': 0.2,
    #        'inviters': 0.05,
    #        'creators': 0.2,
    #        'managers': 0.05}
    return render_template('home.html', **context(
        show='tokenomics',
        # allocation=allocation
    ))


@app.route('/invite/example', methods=['GET'])
def inviteExample():
    ''' example '''
    return 'https://satorinet.io/download/0358f063ce97bc764df0198d1a66188b550fb1d635101d4995e24ca5b8892881fe', 200


@app.route('/neuron/loading', methods=['GET'])
def neuronLoading():
    return (
        '<!DOCTYPE html>'
        '<html>'
        '<head>'
        '<title>Starting Satori Neuron</title>'
        '<script type="text/javascript">setTimeout(function(){window.location.href = "http://127.0.0.1:24601";}, 1000 * 60);</script>'
        '</head>'
        '<body>'
        '<p>Please wait a few minutes while the Satori Neuron boots up. <a href="http://127.0.0.1:24601">Refresh</a>'
        '</p>'
        '</body>'
        '</html>'), 200


###############################################################################
## Routes - Fetched ###########################################################
###############################################################################

@app.route('/early_access/<email>', methods=['GET'])
def earlyAccess(email=None):
    ''' save email to database '''
    try:
        if (
            email is None or
            email == '' or
            '@' not in email or
            # '.' not in email or # could be twitter handle
            # len(email) < 5 or
            len(email) < 2 or
            len(email) > 256
        ):
            return 'OK', 200
        EarlyAccess(email=email).save()
        return 'OK', 200
    except Exception as e:
        return str(e), 400


@app.route('/association/address', methods=['GET'])
def associationAddress():
    ''' evr account of association '''
    if os.environ.get('ENV') == 'prod':
        return jsonify({
            'address': 'https://rvn.cryptoscope.io/address/?address=RKj3w6vqfAopK3Ztwi91vUDEFdv71Qg3ti',
        }), 200
    return jsonify({
        'address': 'https://rvn.cryptoscope.io/address/?address=RKj3w6vqfAopK3Ztwi91vUDEFdv71Qg3ti',
    }), 200


@app.route('/association/token', methods=['GET'])
def associationToken():
    ''' evr account of association '''
    if os.environ.get('ENV') == 'prod':
        return jsonify({
            'token': 'https://evr.cryptoscope.io/asset/?asset_id=081cab6cd370fa387035b9fb5e67e736d7493453',
            'admin': 'https://evr.cryptoscope.io/asset/?asset_id=b0615a9beb5ad1483f2fe4c8d5f546fce5e47fc0',
            'gensis': 'https://evr.cryptoscope.io/tx/?txid=df745a3ee1050a9557c3b449df87bdd8942980dff365f7f5a93bc10cb1080188'}), 200
    return jsonify({
        'token': 'https://rvn.cryptoscope.io/asset/?asset_id=081cab6cd370fa387035b9fb5e67e736d7493453',
        'admin': 'https://rvn.cryptoscope.io/asset/?asset_id=b0615a9beb5ad1483f2fe4c8d5f546fce5e47fc0',
        'gensis': 'https://rvn.cryptoscope.io/tx/?txid=a015f44b866565c832022cab0dec94ce0b8e568dbe7c88dce179f9616f7db7e3'}), 200


@app.route('/votes_for/manifest', methods=['GET'])
def communityVotesForManifest():
    ''' votes are public '''
    try:
        return jsonify({
            'predictors': 0.5,
            'oracles': 0.25,
            'inviters': 0.05,
            'creators': 0.15,
            'managers': 0.05}), 200
    except Exception as e:
        print(e)
        return jsonify({
            'predictors': 0.5,
            'oracles': 0.25,
            'inviters': 0.05,
            'creators': 0.15,
            'managers': 0.05}), 200


###############################################################################
## Routes - API ###############################################################
###############################################################################

# none

###############################################################################
## Entry ######################################################################
###############################################################################
if __name__ == '__main__':
    # serve(app, host='0.0.0.0', port=80)
    if DEVMODE:
        app.run(
            host='0.0.0.0',
            port=5002,
            threaded=True,
            debug=debug,
            use_reloader=False)  # fixes run twice issue
    else:
        certificateLocations = (
            '/etc/letsencrypt/live/satorinet.io/fullchain.pem',
            '/etc/letsencrypt/live/satorinet.io/privkey.pem')
        # app.run(host='0.0.0.0', port=80, threaded=True,
        #        ssl_context=certificateLocations)
        # app.run(host='0.0.0.0', port=5002, threaded=True, debug=debug)
        serve(app, host='0.0.0.0', port=80, url_scheme='https',)
        # gunicorn -c gunicorn.py.ini --certfile /etc/letsencrypt/live/satorinet.io/fullchain.pem --keyfile /etc/letsencrypt/live/satorinet.io/privkey.pem -b 0.0.0.0:443 app:app


# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &
# python .\satoricentral\website\app.py
