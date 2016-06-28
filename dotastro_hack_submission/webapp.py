import os
import base64
import requests
from urllib.parse import parse_qs

from flask import Flask, request, send_from_directory, redirect, render_template
from github import Github
from .add_files import add_files, make_file_contents

GITHUB_AUTH_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'

HACKLIST_REPO = 'dotastro/hacks-collector'

CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']

app = Flask(__name__)


@app.route("/")
def index():
    return redirect(github_authorize())


def github_authorize():
    data = {'client_id': CLIENT_ID,
            'scope': 'repo'}
    pr = requests.Request('GET', GITHUB_AUTH_URL, params=data).prepare()

    return pr.url


@app.route("/submit", methods=['GET'])
def submit():
    data = {'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': request.args['code']}
    res = requests.post(GITHUB_TOKEN_URL, data=data)
    token = parse_qs(res.text)['access_token'][0]

    return render_template('form-validation.html', access_token=token)


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory('form_assets', filename)


@app.route("/create", methods=['POST'])
def create_file():

    token = request.form['access_token']

    title = request.form['title'].lower().replace(' ', '-')
    dotastronumber = request.form['dotastronumber']

    files = {}


    # Process file upload

    if request.files['pic'].filename != "":

        content = request.files['pic'].stream.read()
        mimetype = request.files['pic'].mimetype

        if mimetype.startswith('image/'):
            extension = mimetype.split('/')[1]
        else:
            raise Exception("Unknown mimetype: {0}".format(mimetype))

        content = base64.encodebytes(content).decode('ascii')

        image_filename = "{0}.{1}".format(title, extension)
        files["dotastro{}/{}".format(dotastronumber, image_filename)] = content, 'base64'

    else:

        image_filename = ""

    gh = Github(token)

    main_repo = gh.get_repo(HACKLIST_REPO)
    user_repo = gh.get_user().create_fork(main_repo)

    branches = [b.name for b in user_repo.get_branches()]
    newbranchname = title
    if newbranchname in branches:
        i = 1
        newbranchname = title + '-' + str(i)
        while newbranchname in branches:
            i += 1
            newbranchname = title + '-' + str(i)

    filename = title + '.yml'

    files['dotastro{}/{}'.format(dotastronumber, filename)] = make_file_contents(request, image_filename), 'utf-8'

    add_files(user_repo, newbranchname,
              'Auto-generated entry for "{}"'.format(filename), files)

    prtitle = 'Added entry for hack "{}"'.format(request.form['title'])
    prbody = 'This is a PR auto-generated by a form to record information about the dotAstronomy {} hack "{}"'.format(dotastronumber, request.form['title'])
    base = main_repo.default_branch
    head = gh.get_user().login + ':' + newbranchname

    pr = main_repo.create_pull(title=prtitle, body=prbody, base=base, head=head)

    pr_branch_name = pr.head.label.split(':')[1]
    pr_branch_url = pr.head.repo.html_url + '/tree/' + pr_branch_name

    return render_template('done.html', pr_url=pr.html_url,
                                        pr_branch_name=pr_branch_name,
                                        pr_branch_url=pr_branch_url)
