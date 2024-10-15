#!/usr/bin/env python
# -*- coding: utf-8 -*-

# run with:
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &

'''
This is the Satori Server. It talks to the database. It takes requests from
users on the website, and requests from the nodes. It is the website and node's
server combined into one.
'''
import os
import io
import time
import json
import secrets
import traceback
import datetime as dt
import pandas as pd
import sentry_sdk  # type: ignore
from waitress import serve
from flask import Flask, Response, render_template, jsonify, render_template_string, request
# from satorilib import logging as logging
from satorilib.api.time.time import timestampToDatetime, datetimeToTimestamp, isValidDate
from satorilib.api.time.time import timestampToSeconds, secondsToTimestamp, now
# from satoricentral import logging
from satoricentral import logging as logger
from satoricentral import Wallet, Stream, Referral, EarlyAccess
from satoricentral.server.procedure.manifest import MintManifest
from satoricentral import constants
from satoricentral.server.newrelic_logger import NewRelicLogger

pd.set_option('display.float_format', lambda x: '%.8f' % x)

server_type = os.getenv('server_type')
sentry_dsn = os.getenv('main_sentry')
if server_type == "test":
    sentry_dsn = os.getenv('test_sentry')

if os.getenv('use_sentry') == "true":
    sentry_sdk.init(
        dsn=sentry_dsn,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )

new_relic_api_key = os.getenv('NEW_RELIC_API_KEY')
if new_relic_api_key is not None:
    logging = NewRelicLogger(api_key=new_relic_api_key)
else:
    logging = logger

predictorsReport = None
contributorsReport = None
voteManifestReport = None

###############################################################################
## Setup ######################################################################
###############################################################################

# logging.setup(file='/tmp/server.log', stdoutAndFile=True)
# logging.info('starting satori server...', print=True)


try:
    logging.info('Satori Website started!', color='green')
except Exception as e:
    traceback.print_exc()
    logging.error(f'Exception in app startup: {e}', color='red')


###############################################################################
## Globals ####################################################################
###############################################################################

debug = True
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
DEVMODE = False
ENV = os.environ.get('ENV')


###############################################################################
## Helpers ####################################################################
###############################################################################


def verifyTimestamp(ts, seconds: float = 60*60):
    # TODO: there's a better way to do this. remove this timestamp shit and
    # replace it with the proper way, whether that's jwt or encrypted challenge
    # or whatever. until then just the timecheck.
    # return True
    try:
        if seconds > 0:
            return float(ts) > time.time()-seconds
        if seconds == 0:
            return float(ts) < time.time()
        if seconds < 0:
            return float(ts) < time.time()+seconds
    except Exception as _:
        pass
    timestamp = timestampToDatetime(ts)
    rightNow = now()
    if seconds > 0:
        recentPast = rightNow - dt.timedelta(seconds=seconds)
        return timestamp > recentPast
    if seconds == 0:
        return timestamp < rightNow
    if seconds < 0:
        nearFuture = rightNow - dt.timedelta(seconds=seconds)
        return timestampToDatetime(ts) < nearFuture


def context(title: str = 'Satori', **kwargs):
    return {
        'title': title,
        'stakeRequired': constants.stakeRequired,
        **MintManifest.allocation(),
        **kwargs}


def getPayload(request):
    try:
        return json.loads(request.get_json() or '{}')
    except Exception:
        return json.loads(request.get_data().decode('utf-8'))


###############################################################################
## Functions ##################################################################
###############################################################################

def getIp():
    ''' test ip route '''
    # return f"Your IP address is: {request.headers.get('X-Forwarded-For')}", 200
    if request.headers.get('X-Forwarded-For'):
        ipAddress = request.headers.getlist('X-Forwarded-For')[0]
    elif request.headers.get('X-Real-IP'):
        ipAddress = request.headers.get('X-Real-IP')
    else:
        ipAddress = request.remote_addr
    if isinstance(ipAddress, list):
        ipAddress = ipAddress[0]
    if isinstance(ipAddress, str):
        if ',' in ipAddress:
            ipAddress = ipAddress.split(',')[0]
        return ipAddress
    return ''


def getVoteManifestReport(ref: str = 'latest'):
    from satoricentral import database
    global voteManifestReport
    df, today = database.get.voteManifestDailyReport(
        ref=ref, voteManifestReport=voteManifestReport)
    if (
        isinstance(df, pd.DataFrame) and
        not df.empty and
        ref == 'latest'
    ):
        voteManifestReport = df
    return df, today


def getContributorsReport(ref: str = 'latest'):
    from satoricentral import database
    global contributorsReport
    df, today = database.get.contributorsDailyReport(
        ref=ref, contributorsReport=contributorsReport)
    if (
        isinstance(df, pd.DataFrame) and
        not df.empty and
        ref == 'latest'
    ):
        contributorsReport = df
    return df, today


def getPredictorsReport(ref: str = 'latest', full: bool = False):
    from satoricentral import database
    global predictorsReport
    df, today = database.get.predictorsDailyReport(
        ref=ref, full=full, predictorsReport=predictorsReport)
    if (
        isinstance(df, pd.DataFrame) and
        not df.empty and
        not full and
        ref == 'latest'
    ):
        predictorsReport = df
    return df, today


def getCounts():
    def comma(number):
        return '{:,}'.format(number).split('.')[0]

    from satoricentral import database
    neuronCount, _ = getPredictorsReport()
    predictionCount = database.read('select count(*) from tally')
    oracleCount = database.read(
        'select count(*) from stream where deleted is null and predicting is null;')
    if isinstance(neuronCount, pd.DataFrame):
        neuronCount = len(neuronCount)
    if isinstance(oracleCount, pd.DataFrame):
        oracleCount = oracleCount['count'].values[0]
    if isinstance(predictionCount, pd.DataFrame):
        predictionCount = predictionCount['count'].values[0] * 1.5
    return {
        'oracleCount': comma(oracleCount or 2500),
        'neuronCount': comma(neuronCount or 20000),
        'predictionCount': comma(predictionCount or 4000000)}

###############################################################################
## Errors #####################################################################
###############################################################################


@app.errorhandler(404)
def not_found(e):
    return '404', 404

###############################################################################
## Routes - static ############################################################
###############################################################################


@app.route('/association/originaladdress', methods=['GET'])
def associationOriginalAddress():
    ''' evr account of association '''
    if os.environ.get('ENV') == 'prod':
        return jsonify({
            'address': 'ETbmMAt4VJJAELoZHP9Qq5rzG1xdrFWsBG',
            'link': 'https://evr.cryptoscope.io/address/?address=ETbmMAt4VJJAELoZHP9Qq5rzG1xdrFWsBG',
        }), 200
    return jsonify({
        'address': 'RKj3w6vqfAopK3Ztwi91vUDEFdv71Qg3ti',
        'link': 'https://rvn.cryptoscope.io/address/?address=RKj3w6vqfAopK3Ztwi91vUDEFdv71Qg3ti',
    }), 200


@app.route('/association/address', methods=['GET'])
def associationAddress():
    ''' evr account of association '''
    if os.environ.get('ENV') == 'prod':
        return jsonify({
            'address': 'EZpVQ6VDbGzZZoooi7DPWtudav88v1CtB4',
            'link': 'https://evr.cryptoscope.io/address/?address=EZpVQ6VDbGzZZoooi7DPWtudav88v1CtB4',
        }), 200
    return jsonify({
        'address': 'RKj3w6vqfAopK3Ztwi91vUDEFdv71Qg3ti',
        'link': 'https://rvn.cryptoscope.io/address/?address=RKj3w6vqfAopK3Ztwi91vUDEFdv71Qg3ti',
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


@app.route('/ip', methods=['GET'])
def ip():
    ''' test ip route '''
    return f"Your IP address is: {getIp()}", 200


@app.route('/verify/scripthash', methods=['GET'])
def verify_scripthash():
    ''' returns a list of hashes suitable for execution '''
    return jsonify(['8be3ce334e29e81f3a0160b9e1092e1f8aba363e41bc67251a7528a378ff18d5']), 200


@app.route('/time', methods=['GET'])
def timeEndpoint():
    ''' test time route '''
    return datetimeToTimestamp(now()), 200


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
## Routes - Pages #############################################################
###############################################################################


# for testing
# @app.route('/admin', methods=['GET'])
# def admin(term=None):
#  try:
#  SatoriPubSubConn()
#  return generateAdminKey(), 200
#  except Exception as e:
#  return str(e), 400

@app.route('/newrelictest', methods=['GET'])
def newrelictest():
    logging.info("Test Info")
    logging.warning("Test Warning")
    logging.error("Test Error")
    logging.error("Try", "Error 1", "Error 2")
    logging.warning("Try", "Warning 1", "Warning 2")
    return "ok", 200


@app.route('/', methods=['GET'])
@app.route('/home', methods=['GET'])
@app.route('/search/<term>', methods=['GET'])
def search(term=None):
    ''' searching for a stream '''
    try:
        return render_template(
            'home.html',
            **context(show='search', searchResults=searchTerm(term)[0]),
            **getCounts(),
        )
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
    if isinstance(ref, str) and len(ref) == 66:
        # associate the ip address with the pubkey provided.
        wallet = Wallet(pubkey=ref)
        if wallet.get(inplace=True, noneOk=True) == None:
            wallet.save()
            wallet.get(inplace=True)
        Referral(ip=getIp(), wallet_id=wallet.id).save()
        # associate the ip address with the pubkey that wants this downloaded.
        return render_template('home.html', **context(show='download', ref=ref))
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
        # stakeRequired=constants.stakeRequired,
        # allocation=allocation
    ),
    )


###############################################################################
## Routes - Search ############################################################
###############################################################################

@app.route('/search/<term>', methods=['POST'])
def searchTerm(term=None):
    ''' searching for a stream '''
    try:
        if term is None:
            return [], 200
        payload = {k: term for k in Stream.searchColumns()}
        streams = Stream(**payload).search(limit=100)
        if streams is None:
            return 'no streams', 400
        return Stream.asJson(streams, omitIds=False), 200  # type: ignore
    except Exception as e:
        return str(e), 400


@app.route('/see/prediction/<streamId>', methods=['GET'])
def seePrediction(streamId: int):
    '''
    get all the streams that predict this streamId and get the latest
    prediction (observation) for all of those streams
    '''
    dfHist, avg = Stream.getAvgPredictionOf(streamId)
    result = list(dfHist[['ts', 'value']].to_records(index=False))
    result = [(x[0], x[1]) for x in result]
    return jsonify({'history': result, 'avg': avg}), 200


###############################################################################
## Routes - Events ############################################################
###############################################################################


@app.route('/events/search/<term>', methods=['GET'])
def eventsSearch(term=None):
    ''' get all (non-predictive) datastreams for a given search term '''
    msg = searchTerm(term)[0]
    return Response(f'data:{msg}\n\n', mimetype='text/event-stream')


@app.route('/events/prediction/<streamId>', methods=['GET'])
def eventsPrediction(streamId: int):
    '''
    get all the streams that predict this streamId and get the latest
    prediction (observation) for all of those streams
    '''
    def _timeChecksOut(prediction, seconds: float):
        return (
            (
                prediction.kwargs.get('prediction_time') is not None and
                # not too far in past
                verifyTimestamp(
                    ts=prediction.kwargs.get('prediction_time'),
                    seconds=seconds) and
                # not too far in future
                verifyTimestamp(
                    ts=prediction.kwargs.get('prediction_time'),
                    seconds=-1*seconds)) or
            (prediction.kwargs.get('prediction_ts') is not None and
             verifyTimestamp(
                ts=prediction.kwargs.get('prediction_ts'),
                seconds=seconds)))

    def _getPredictions(stream: Stream, seconds: float):
        if seconds <= 30:
            return stream.predictions()
        return [
            prediction
            for prediction in stream.predictions()
            if _timeChecksOut(prediction, seconds)]

    def _getWhen(timestamp: str):
        try:
            return secondsToTimestamp(timestampToSeconds(timestamp))
        except Exception as _:
            # without a cadence or explicit time, we can't know when it is
            # predicting so until we get an average cadence, we make a
            # heuristic guess - assume now is half way to the target time
            return now() + (now() - timestampToDatetime(timestamp))

    stream = Stream(id=streamId)
    observations = stream.observations()
    try:
        cadence = int(stream.cadence)
    except Exception:
        cadence = 0
    predictions = _getPredictions(
        stream=stream,
        seconds=(
            (
                now() - timestampToDatetime(observations[-1].ts)
            ).total_seconds()
            if observations is not None and len(observations) > 0
            else cadence))
    if predictions is None or len(predictions) == 0:
        msg = '[]'
    else:
        # not necessary, we'll just parse out what we care about...
        # observations = [Observation(
        #        value=prediction.kwargs.get('prediction_value'),
        #        value=prediction.kwargs.get('prediction_time'),
        #        value=prediction.kwargs.get('prediction_ts'))
        # for prediction in predictions]
        try:
            avg = sum([prediction.kwargs.get('prediction_value')
                      for prediction in predictions]) / len(predictions)
        except TypeError:
            try:
                avg = sum([float(prediction.kwargs.get('prediction_value'))
                          for prediction in predictions]) / len(predictions)
            except Exception:
                avg = None
        except Exception:
            avg = None

        msg = json.dumps([
            {
                'source': prediction.source,
                'stream': prediction.stream,
                'target': prediction.target,
                'prediction': prediction.kwargs.get('prediction_value'),
                'time': prediction.kwargs.get('prediction_time'),
                'ts': prediction.kwargs.get('prediction_ts'),
                'when': _getWhen(prediction.kwargs.get('prediction_ts')),
                'avg': avg}
            for prediction in predictions
            if prediction.kwargs.get('prediction_value') is not None])
    return Response(f'data:{msg}\n\n', mimetype='text/event-stream')


###############################################################################
## Routes - Reports ###########################################################
###############################################################################


@app.route('/reports/stats/daily/predictors/<ref>', methods=['GET'])
def predictorsDailyReportStats(ref: str = 'latest'):
    ''' csv report from database '''
    df, today = getPredictorsReport(ref=ref)
    if not isinstance(df, pd.DataFrame):
        return 'no data found', 400
    try:
        total_competing_neuron_count = len(df)
        self_staked_neuron_count = len(
            df[df['balance'] > constants.stakeRequired])
        delegated_stake_neuron_count = len(df[df['delegated_stake'] > 0])
        pool_rewarded_neuron_count = len(df[df['pool_stake'] > 0])
        pool_unrewarded_neuron_count = len(
            df[df['balance'] + df['delegated_stake'] + df['pool_stake'] == 0])
        pool_size = df['pool_stake'].sum()
        pool_rewarded_score = df[df['pool_stake']
                                 > 0]['score'].mean()*len(df)
        self_stake_score = df[df['balance'] >
                              constants.stakeRequired]['score'].mean()*len(df)
        delegated_stake_score = df[df['delegated_stake']
                                   > 0]['score'].mean()*len(df)
        return jsonify({
            'Date': today,
            'Competing Neurons': total_competing_neuron_count,
            'Self-staked Neurons': self_staked_neuron_count,
            'Delegated-staked Neurons': delegated_stake_neuron_count,
            'Pool-staked Neurons': pool_rewarded_neuron_count,
            'Pool-unstaked Neuron': pool_unrewarded_neuron_count,
            'Pool Size (SATORI)': pool_size,
            'Average Score of Pool-staked Neurons': pool_rewarded_score,
            'Average Score of Self-staked Neurons': self_stake_score,
            'Average Score of Delegated-staked Neurons': delegated_stake_score,
        }), 200
    except Exception as e:
        return f'error: {e}'


@app.route('/reports/daily/predictors/<ref>', methods=['GET', 'POST'])
def predictorsDailyReport(ref: str = 'latest'):
    ''' csv report from database '''
    full = False
    if request.method == 'POST':
        payload = getPayload(request)
        if payload is None:
            return 'payload json', 400
        if payload.get('adminrequest') == 'fullreport':
            full = True
    df, today = getPredictorsReport(ref=ref, full=full)
    if not isinstance(df, pd.DataFrame):
        return 'no data found', 400
    # Create a CSV in memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, float_format='%.8f')
    csv_buffer.seek(0)
    # Use send_file to send the CSV as a downloadable file
    return Response(
        csv_buffer,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment;filename=predictors-{today}.csv'})


@app.route('/reports/daily/lowest/<ref>', methods=['GET'])
def lowestPerformersDailyReport(ref: str):
    ''' csv report from database '''
    from satoricentral import database
    if 'report_lowest' not in database.inspector.get_table_names():
        return 'report not found', 400
    if ref == 'latest' or not isValidDate(ref):
        today = dt.datetime.today().strftime('%Y-%m-%d')
    else:
        today = ref
    df_last_timestamp = database.read(
        query="""
            SELECT ts
            FROM report_lowest
            WHERE ts::date = %s
            ORDER BY ts DESC
            LIMIT 1;""",
        params=[today])
    if df_last_timestamp is not None and not df_last_timestamp.empty:
        last_ts = df_last_timestamp.iloc[0]['ts']
        df = database.read(
            query="""
                SELECT
                    wallet as worker_address,
                    reward_address as reward_address,
                    placement,
                    satori as potential_stake,
                    proxy as delegated_stake
                FROM report_lowest
                WHERE ts = %s;""",
            params=[last_ts])
    else:
        df = None
    if not isinstance(df, pd.DataFrame):
        return 'no data found', 400
    # Create a CSV in memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, float_format='%.8f')
    csv_buffer.seek(0)
    # Use send_file to send the CSV as a downloadable file
    return Response(
        csv_buffer,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment;filename=lowest_performers-{today}.csv'})


@app.route('/reports/daily/contributors/<ref>', methods=['GET'])
def contributorsDailyReport(ref: str = 'latest'):
    ''' csv report from database '''
    df, today = getContributorsReport(ref=ref)
    if not isinstance(df, pd.DataFrame):
        return 'no data found', 400
    # Create a CSV in memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, float_format='%.8f')
    csv_buffer.seek(0)
    # Use send_file to send the CSV as a downloadable file
    return Response(
        csv_buffer,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment;filename=contributors-{today}.csv'})


@app.route('/reports/daily/votes/manifest/<ref>', methods=['GET'])
def voteManifestDailyReport(ref: str = 'latest'):
    ''' csv report from database '''
    df, today = getVoteManifestReport(ref=ref)
    if not isinstance(df, pd.DataFrame):
        return 'no data found', 400
    # Create a CSV in memory
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, float_format='%.8f')
    csv_buffer.seek(0)
    # Use send_file to send the CSV as a downloadable file
    return Response(
        csv_buffer,
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment;filename=manifest-{today}.csv'})


###############################################################################
## Routes - API ###############################################################
###############################################################################


@app.route('/votes_for/manifest', methods=['GET'])
def communityVotesForManifest():
    ''' votes are public '''
    try:
        return jsonify(MintManifest.allocation()), 200
    except Exception as e:
        return jsonify({
            'predictors': 0.5,
            'oracles': 0.2,
            'inviters': 0.05,
            'creators': 0.2,
            'managers': 0.05}), 200


@app.route('/audit/delegates', methods=['GET'])
def auditDelegatesHTML():
    df = Wallet.rewardRelationship()
    table_html = df.to_html(classes='table table-striped', index=False)
    html = f"""
    <html>
    <head>
        <title>Reward Relationship</title>
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css">
    </head>
    <body>
        <div class="container">
            <h2>Reward Relationship Table</h2>
            {table_html}
        </div>
    </body>
    </html>
    """
    return render_template_string(html)


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
        serve(app, host='0.0.0.0', port=80, url_scheme='https')
        # gunicorn -c gunicorn.py.ini --certfile /etc/letsencrypt/live/satorinet.io/fullchain.pem --keyfile /etc/letsencrypt/live/satorinet.io/privkey.pem -b 0.0.0.0:443 app:app


# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &
# > python satori\web\app.py


# python .\satoricentral\web\app.py
