import os
import requests
from fast_arrow.util import get_last_path
from fast_arrow.resources.account import Account
from fast_arrow.exceptions import AuthenticationError
from fast_arrow.exceptions import NotImplementedError
from file_tools.json_file import import_json, export_json

CLIENT_ID = "c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS"

HTTP_ATTEMPTS_MAX = 2


class Client(object):

    def __init__(self, **kwargs):
        self.options = kwargs
        self.account_id = None
        self.account_url = None
        self.access_token = None
        self.refresh_token = None
        self.mfa_code = None
        self.scope = None
        self.authenticated = False
        self.certs = os.path.join(
            os.path.dirname(__file__), 'ssl_certs/certs.pem')

    def authenticate(self):
        '''
        Authenticate using data in `options`
        '''

        cur_path = os.path.abspath(__file__)
        config = import_json('../data/config.json', path=cur_path)
        auth_data = import_json('../data/login_data.json', path=cur_path)

        self.options["username"] = self.options["username"] if 'username' in self.options else config['u_n'].b64_dec()

        if 'Bearer' not in auth_data['auth']:

            password = self.options["password"] if self.options["password"] is not None else config['p_w'].b64_dec()

            if "username" in self.options and "password" in self.options:
                self.login_oauth2(
                    self.options["username"],
                    password,
                    self.options.get('device_token'),
                    self.options.get('mfa_code'),
                    cur_path)
            elif "access_token" in self.options:
                if "refresh_token" in self.options:
                    self.access_token = self.options["access_token"]
                    self.refresh_token = self.options["refresh_token"]
                    self.__set_account_info()
            else:
                self.authenticated = False

        else:
            self.access_token = auth_data['access_token']
            self.refresh_token = auth_data['refresh_token']
            self.authenticated = True

        return self.authenticated

    def get(self, url=None, params=None, retry=True):
        '''
        Execute HTTP GET
        '''
        headers = self._gen_headers(self.access_token, url)
        attempts = 1
        while attempts <= HTTP_ATTEMPTS_MAX:
            try:
                res = requests.get(url,
                                   headers=headers,
                                   params=params,
                                   timeout=15,
                                   verify=self.certs)
                res.raise_for_status()
                return res.json()
            except requests.exceptions.RequestException as e:
                attempts += 1
                if res.status_code in [400]:
                    raise e
                elif retry and res.status_code in [403]:
                    self.relogin_oauth2()

    def post(self, url=None, payload=None, retry=True):
        '''
        Execute HTTP POST
        '''
        headers = self._gen_headers(self.access_token, url)
        attempts = 1
        while attempts <= HTTP_ATTEMPTS_MAX:
            try:
                res = requests.post(url, headers=headers, data=payload,
                                    timeout=15, verify=self.certs)
                res.raise_for_status()
                if res.headers['Content-Length'] == '0':
                    return None
                else:
                    return res.json()
            except requests.exceptions.RequestException as e:
                attempts += 1
                if res.status_code in [400, 429]:
                    raise e
                elif retry and res.status_code in [403]:
                    self.relogin_oauth2()

    def _gen_headers(self, bearer, url):
        '''
        Generate headders, adding in Oauth2 bearer token if present
        '''
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": ("en;q=1, fr;q=0.9, de;q=0.8, ja;q=0.7, " +
                                "nl;q=0.6, it;q=0.5"),
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) " +
                           "AppleWebKit/537.36 (KHTML, like Gecko) " +
                           "Chrome/68.0.3440.106 Safari/537.36"),

        }
        if bearer:
            headers["Authorization"] = "Bearer {0}".format(bearer)
        if url == "https://api.robinhood.com/options/orders/":
            headers["Content-Type"] = "application/json; charset=utf-8"
        return headers

    def login_oauth2(self, username, password, device_token=None, mfa_code=None, cur_path=None):
        '''
        Login using username and password
        '''
        data = {
            "grant_type": "password",
            "scope": "internal",
            "client_id": CLIENT_ID,
            "expires_in": 86400,
            "password": password,
            "username": username,
            "device_token": device_token
        }
        if mfa_code is not None:
            data['mfa_code'] = mfa_code
        url = "https://api.robinhood.com/oauth2/token/"
        res = self.post(url, payload=data, retry=False)

        if res is None:
            if mfa_code is None:
                msg = ("Client.login_oauth2(). Could not authenticate. Check "
                       + "username and password.")
                raise AuthenticationError(msg)
            else:
                msg = ("Client.login_oauth2(). Could not authenticate. Check" +
                       "username and password, and enter a valid MFA code.")
                raise AuthenticationError(msg)
        elif res.get('mfa_required') is True:
            msg = "Client.login_oauth2(). Couldn't authenticate. MFA required."
            raise AuthenticationError(msg)

        self.access_token = res["access_token"]
        self.refresh_token = res["refresh_token"]
        self.mfa_code = res["mfa_code"]
        self.scope = res["scope"]
        self.__set_account_info()
        if cur_path is not None:
            export_json ({
                        'access_token': self.access_token,
                        'refresh_token': self.refresh_token,
                        'auth': 'Bearer ' + self.auth_token
                    }, '../data/login_data.json', path=cur_path, indent=4)
        return self.authenticated

    def __set_account_info(self):
        account_urls = Account.all_urls(self)
        if len(account_urls) > 1:
            msg = ("fast_arrow 'currently' does not handle " +
                   "multiple account authentication.")
            raise NotImplementedError(msg)
        elif len(account_urls) == 0:
            msg = "fast_arrow expected at least 1 account."
            raise AuthenticationError(msg)
        else:
            self.account_url = account_urls[0]
            self.account_id = get_last_path(self.account_url)
            self.authenticated = True

    def relogin_oauth2(self):
        '''
        (Re)login using the Oauth2 refresh token
        '''
        url = "https://api.robinhood.com/oauth2/token/"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "scope": "internal",
            "client_id": CLIENT_ID,
            "expires_in": 86400,
        }
        res = self.post(url, payload=data, retry=False)
        self.access_token = res["access_token"]
        self.refresh_token = res["refresh_token"]
        self.mfa_code = res["mfa_code"]
        self.scope = res["scope"]

    def logout_oauth2(self):
        '''
        Logout for given Oauth2 bearer token
        '''
        url = "https://api.robinhood.com/oauth2/revoke_token/"
        data = {
            "client_id": CLIENT_ID,
            "token": self.refresh_token,
        }
        res = self.post(url, payload=data)
        if res is None:
            self.account_id = None
            self.account_url = None
            self.access_token = None
            self.refresh_token = None
            self.mfa_code = None
            self.scope = None
            self.authenticated = False
            return True
        else:
            raise AuthenticationError("fast_arrow could not log out.")
