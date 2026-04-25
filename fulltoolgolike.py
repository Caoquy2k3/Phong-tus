#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool tự động chạy nhiệm vụ Golike - Phiên bản gộp
Hỗ trợ: Instagram, Threads, LinkedIn, Pinterest, YouTube, Bluesky, TikTok (ADB)
"""

import json
import re
import sys
import signal
import os
import random
import time
import hashlib
import string
import base64
import urllib.parse
import platform
import shutil
from time import sleep

# DNS và requests
import dns.resolver
import requests as std_requests
from curl_cffi import requests
import fake_useragent as ua

# ==================== XỬ LÝ SIGINT ====================
def handle_sigint(sig, frame):
    os._exit(0)

signal.signal(signal.SIGINT, handle_sigint)

# ==================== USER AGENT ====================
user_agent = ua.UserAgent(os=["windows"], fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# ==================== DNS RESOLVER ====================
resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

# ==================== CLASS INSTAGRAM ====================
class INSTAGRAM():
    def __init__(self, cookies):
        self.cookies = cookies
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'dnt': '1',
            'origin': 'https://www.instagram.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.instagram.com',
            'sec-ch-prefers-color-scheme': 'dark',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="135.0.7049.85", "Not-A.Brand";v="8.0.0.0", "Chromium";v="135.0.7049.85"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent.random,
            'x-asbd-id': '359341',
            'x-bloks-version-id': '446750d9733aca29094b1f0c8494a768d5742385af7ba20c3e67c9afb91391d8',
            'x-csrftoken': cookies.split("csrftoken=")[1].split(";")[0] if "csrftoken=" in cookies else "0",
            'x-fb-friendly-name': 'usePolarisFollowMutation',
            'x-fb-lsd': 'sLgifsATkzEGmbMOrCN2zO',
            'x-ig-app-id': '936619743392459',
            'x-root-field-name': 'xdt_create_friendship',
            'cookie': cookies,
        }

    def GETINFO(self):
        try:
            response = requests.get("https://www.instagram.com/", headers=self.headers).text
            userID = re.findall('userID":.*?,', response)
            userID1 = userID[0].split(':"')[1].split('",')[0]
            DTSG = re.findall("DTSGInitialData.*?},", response)[0].split('":"')[1].split('"}')[0]
            match = re.search(r'"LSD"\s*,\s*\[\s*],\s*\{"token"\s*:\s*"([^"]+)"', response)
            lsd_token = match.group(1)
            return userID1, DTSG, lsd_token
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def FOLLOW(self, av, dtsg, user_id, cookies, link, lsd_token):
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'dnt': '1',
            'origin': 'https://www.instagram.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': link,
            'sec-ch-prefers-color-scheme': 'dark',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="135.0.7049.85", "Not-A.Brand";v="8.0.0.0", "Chromium";v="135.0.7049.85"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent.random,
            'x-asbd-id': '359341',
            'x-bloks-version-id': '446750d9733aca29094b1f0c8494a768d5742385af7ba20c3e67c9afb91391d8',
            'x-csrftoken': cookies.split("csrftoken=")[1].split(";")[0] if "csrftoken=" in cookies else "0",
            'x-fb-friendly-name': 'usePolarisFollowMutation',
            'x-fb-lsd': lsd_token,
            'x-ig-app-id': '936619743392459',
            'x-root-field-name': 'xdt_create_friendship',
            'cookie': cookies,
        }
        data = {
            'av': av,
            'fb_dtsg': dtsg,
            'fb_api_caller_class': 'RelayModern',
            'fb_api_req_friendly_name': 'usePolarisFollowMutation',
            'variables': '{"target_user_id":"' + str(user_id) + '","container_module":"profile","nav_chain":"PolarisFeedRoot:feedPage:1:via_cold_start,PolarisProfilePostsTabRoot:profilePage:2:unexpected"}',
            'doc_id': '9660047674090784',
        }
        try:
            response = requests.post('https://www.instagram.com/graphql/query', headers=headers, data=data, impersonate="chrome120").json()
            if 'xdt_create_friendship' in response['data']:
                if response['data']['xdt_create_friendship']['friendship_status']['following'] == True and response['status'] == "ok":
                    return True
                else:
                    return False
            elif 'xdt_api__v1__friendships__create__target_user_id' in response['data']:
                if response['data']['xdt_api__v1__friendships__create__target_user_id']['friendship_status']['following'] == True and response['status'] == "ok":
                    return True
                else:
                    return False
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def LIKE(self, av, dtsg, post_id, cookies, link, lsd_token):
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'dnt': '1',
            'origin': 'https://www.instagram.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': link,
            'sec-ch-prefers-color-scheme': 'dark',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="135.0.7049.85", "Not-A.Brand";v="8.0.0.0", "Chromium";v="135.0.7049.85"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': user_agent.random,
            'x-asbd-id': '359341',
            'x-bloks-version-id': '446750d9733aca29094b1f0c8494a768d5742385af7ba20c3e67c9afb91391d8',
            'x-csrftoken': cookies.split("csrftoken=")[1].split(";")[0] if "csrftoken=" in cookies else "0",
            'x-fb-friendly-name': 'usePolarisFollowMutation',
            'x-fb-lsd': lsd_token,
            'x-ig-app-id': '936619743392459',
            'x-root-field-name': 'xdt_create_friendship',
            'cookie': cookies,
        }
        data = {
            'av': av,
            'fb_dtsg': dtsg,
            'fb_api_caller_class': 'RelayModern',
            'fb_api_req_friendly_name': 'usePolarisLikeMediaLikeMutation',
            'variables': '{"media_id":"' + str(post_id) + '","container_module":"feed_timeline"}',
            'doc_id': '9595477160535898',
        }
        try:
            response = requests.post('https://www.instagram.com/graphql/query', headers=headers, data=data, impersonate="chrome120").json()
            if response['extensions']['is_final'] == True and response['status'] == "ok":
                return True
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def COMMENT(self, av, dtsg, taget_id, comment, cookies, link, lsd_token):
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'cache-control': 'no-cache',
            'content-type': 'application/x-www-form-urlencoded',
            'dnt': '1',
            'origin': 'https://www.instagram.com',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': link,
            'sec-ch-prefers-color-scheme': 'dark',
            'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="135.0.7049.85", "Not-A.Brand";v="8.0.0.0", "Chromium";v="135.0.7049.85"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
            'x-asbd-id': '359341',
            'x-bloks-version-id': '446750d9733aca29094b1f0c8494a768d5742385af7ba20c3e67c9afb91391d8',
            'x-csrftoken': cookies.split("csrftoken=")[1].split(";")[0] if "csrftoken=" in cookies else "0",
            'x-fb-friendly-name': 'usePolarisFollowMutation',
            'x-fb-lsd': lsd_token,
            'x-ig-app-id': '936619743392459',
            'x-root-field-name': 'xdt_create_friendship',
            'cookie': cookies,
        }
        comment_en = urllib.parse.quote(comment)
        fb_dtsg = urllib.parse.quote(dtsg)
        data = 'av=' + str(av) + '&__d=www&__user=0&__a=1&__req=2l&__hs=20197.HYP%3Ainstagram_web_pkg.2.1...1&dpr=1&__ccg=GOOD&__rev=1022052427&__s=bgt40q%3Aqz5wz7%3A5bue8v&__hsi=7494937329156458506&__dyn=7xeUjG1mxu1syUbFp41twpUnwgU7SbzEdF8aUco2qwJxS0DU2wx609vCwjE1EE2Cw8G11wBz81s8hwGxu786a3a1YwBgao6C0Mo2iyo7u3ifK0EUjwGzEaE2iwNwmE7G4-5o4q3y1Sw62wLyESE7i3vwDwHg2ZwrUdUbGwmk0zU8oC1Iwqo5p0OwUQp1yUb8jK5V89F8uwm8jxK2K2G13wnoK9x60gm5o&__csr=h42v0AWZnsr4R9bfsjtirTHWhfUCqidTKicHOaymhpYx9rV95ncGX8YxVqggjFoKF_AhAqVW-aiIyZ4GjyA7k8AbBhrgSVUiww_J1pvFIEHt28yfgjBVqoiBK4mqWhqDx6cBCCxDiGcUyWGijx2LwPBx62anhEix-ibgixa00kbG1Fa0s20gSbxa1rDg1ar8m2Z0tA0eGw39U3hw1iXgbE4TxgUOq0LFkb4CK2l0DhVU-0jyO02b81tP0wCF0NCDwBgrws9k9w12syjoF1giq688846vm0iu6Wdw0r2E0ZK02uC&__hsdp=geyk_7kW7Ckh6cCob2QVjuyIy45q24uzkJMbO8dSpbiKbgEMQvGjKPy860k5Qbx6cj5CxuERx8V88UKdzVpr8ax8wB1S2G26a8i4648G8wEwZg4d1iU8827DKm3iubCypUuw44x6u0E8-0hu1pwVw77w8y1owXwjGwiA69j0k84Gu6UgyUbA1Dw921bwmodqoKayU8o2GwPwnE424E5S2a&__hblpi=048wd-0g20LUnxa1mwxxa48iyEy2y3R0mo9827DKm3iubCypUuw44x6u0E8-0hu1pwVw77w8y1owXw9N1ykM521aDxK48K2V0pU2gwiU5C3mCbyEK260GEcU5W10xa1twyw&__hblpn=0-xG2e4ocE8EqJoypokzE23UXUO15xS1_UG79Gxng8ULy8hw_iDGQ48bWxy3ei49HxG2i4FUoByAim2a5EjUjwwz9ocVo-2q0wodUnwcy2O0Tp8swd-1uwoE2Ex-0kq1aghU2Rybgjwk8owYAwCwJzo5W1fwj8-2S489ofo2fzo4W2-3e2K7E6u4Ebag2fw&__comet_req=7&fb_dtsg=' + fb_dtsg + '&jazoest=26347&lsd=ZNOd9VGbAyRFBHYAjvpqN3&__spin_r=1022052427&__spin_b=trunk&__spin_t=1745051082&__crn=comet.igweb.PolarisMobileAllCommentsRouteNext&fb_api_caller_class=RelayModern&fb_api_req_friendly_name=PolarisPostCommentInputRevampedMutation&variables=%7B%22connections%22%3A%5B%22client%3Aroot%3A__PolarisPostComments__xdt_api__v1__media__media_id__comments__connection_connection(data%3A%7B%7D%2Cmedia_id%3A%5C%22' + str(taget_id) + '%5C%22%2Csort_order%3A%5C%22popular%5C%22)%22%5D%2C%22request_data%22%3A%7B%22comment_text%22%3A%22' + comment_en + '%22%7D%2C%22media_id%22%3A%22' + str(taget_id) + '%22%7D&server_timestamps=true&doc_id=7980226328678944'
        try:
            response = requests.post('https://www.instagram.com/graphql/query', headers=headers, data=data, impersonate="chrome120").json()
            if response['extensions']['is_final'] == True and response['status'] == "ok":
                return True
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False


# ==================== CLASS TWITTER (X) ====================
class Twitter():
    def __init__(self, cookies, auth):
        self.cookies = cookies
        self.auth = auth

    def GETDATA(self):
        try:
            headers = {
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': user_agent.random,
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'cookie': self.cookies
            }
            response = requests.get('https://x.com/home', headers=headers, impersonate="chrome120")
            if response.status_code == 200:
                match = re.search(r'"screen_name"\s*:\s*"([^"]+)"', response.text)
                if match:
                    screen_name = match.group(1)
                    return screen_name
                else:
                    return False
            else:
                return False
        except:
            return False

    def Follow(self, obj_id):
        try:
            csrftoken = self.cookies.split("ct0=")[1].split(";")[0]
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
                'authorization': self.auth,
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'dnt': '1',
                'origin': 'https://x.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://x.com/',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent.random,
                'x-client-transaction-id': 'm2mm1IkP77UW4kOmseb0zVZ+g+Y2HvgAM9HDnUda9fVf8taUHDBTbMEueUiq8FBCTIlDo58bDzX/tLVmOhU1Fgf+9B6pmA',
                'x-csrf-token': csrftoken,
                'x-twitter-active-user': 'yes',
                'x-twitter-auth-type': 'OAuth2Session',
                'x-twitter-client-language': 'en',
                'x-xp-forwarded-for': 'b4b9e0916223cb529b6734ffadf5e0334f1307d07194d9535053727fdeff44a8a1ba7df8c29d408a21668e955045a4b3c075baf5675a9924ed304e2a38bd1316bf0609d328009c75029816b07b457e221c44c34c09052a35aca779fd969f4b26c530375282f9d9f77925ebcf32dc0db017adba5fece73cd7bdc57033c73478a0348eb2aad31c98922c3a4b2421d111ab9c69db9692f6aab9df97cf44ea56bc6277b5b65c83a03c10a85781665ce6a4811312591060640cfde1127746a08bc2675a6e74d556c2b0f1c39e86bf32a72a39d6ebfe607467c8c5d92e65823588f834f112e0ce044db055d2944b70843f5a8c639e51a6dbd8674cc35a',
                'cookie': self.cookies,
            }
            data = {
                'include_profile_interstitial_type': '1',
                'include_blocking': '1',
                'include_blocked_by': '1',
                'include_followed_by': '1',
                'include_want_retweets': '1',
                'include_mute_edge': '1',
                'include_can_dm': '1',
                'include_can_media_tag': '1',
                'include_ext_is_blue_verified': '1',
                'include_ext_verified_type': '1',
                'include_ext_profile_image_shape': '1',
                'skip_status': '1',
                'user_id': str(obj_id),
            }
            response = requests.post('https://x.com/i/api/1.1/friendships/create.json', headers=headers, data=data)
            if response.status_code == 200:
                return True
            else:
                return False
        except:
            return False

    def Like(self, obj_id):
        try:
            csrftoken = self.cookies.split("ct0=")[1].split(";")[0]
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
                'authorization': self.auth,
                'cache-control': 'no-cache',
                'content-type': 'application/json',
                'dnt': '1',
                'origin': 'https://x.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://x.com/home',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent.random,
                'x-client-transaction-id': '4ivVeqK6IfDtTnzbMIOFXgh/D/knhTPddIexgSIVseVPoxlCMCIUUShomIE3YTaEp/E72ubxyKNKT+nb8STGtWMxZFbZ4Q',
                'x-csrf-token': csrftoken,
                'x-twitter-active-user': 'yes',
                'x-twitter-auth-type': 'OAuth2Session',
                'x-twitter-client-language': 'en',
                'x-xp-forwarded-for': 'f8bb9b012e51e296892cea226f44c90686a2012be6d3a2570de5ddd9fb6223c59aee86cdcf7307ec78b3dcd3dcd462a7fcff1711088683face4dfd893bc3b92607f76baa0a33169be21a2fc44f4e16bdc71313fd9039f59dcfa78fd35766f5f0acc09e8f2426a20068a456872770cbd6ebd87462eebbbcd454b1d0e2288fe87e5943d012d33d755e69c48db81e707fb93078ef3420a6f453e50b6e3476ae0697d95d872c67f2018e70dc5e19448e2710f7ed5fe4267e5fc65df877e21eca346ae13d07b2d233a2790afe81abfdf81fbb46d43c217cf4e6fd0ea2d43427bb25b349e8373fd0a7300d7881ada42f550925dc2c7924c01f6adc99e057',
                'cookie': self.cookies,
            }
            json_data = {
                'variables': {
                    'tweet_id': str(obj_id),
                },
                'queryId': 'lI07N6Otwv1PhnEgXILM7A',
            }
            response = requests.post('https://x.com/i/api/graphql/lI07N6Otwv1PhnEgXILM7A/FavoriteTweet', headers=headers, json=json_data, impersonate='chrome120')
            if response.status_code == 200:
                if response.json()['data']['favorite_tweet'] == "Done":
                    return True
                else:
                    return False
            else:
                return False
        except:
            return False

    def cmt(self, obj_id, cmt_message):
        try:
            csrftoken = self.cookies.split("ct0=")[1].split(";")[0]
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
                'authorization': self.auth,
                'cache-control': 'no-cache',
                'content-type': 'application/json',
                'dnt': '1',
                'origin': 'https://x.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://x.com/',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent.random,
                'x-client-transaction-id': 'DgnXFbkADGhjxcfGFjOxFfxPXqh9JFDQXyVYGryI0XO8Ng6IK1Ir7JG35/Snxy+a2vbUNgpWX8b3tW5LFWf8J7JAePUNDQ',
                'x-csrf-token': csrftoken,
                'x-twitter-active-user': 'yes',
                'x-twitter-auth-type': 'OAuth2Session',
                'x-twitter-client-language': 'en',
                'x-xp-forwarded-for': '8a81b15de6c7ae11fff9579ba50b48667e2f412269ea88d9ae979b3af7b31e8ebc91a1f6ee2fbfdce693d8f9472caba4307dbd3f3fe2c6ea47c740d4c5554c5462288e81d617e5d4c3c7a993af26bcab09c2fa23c53a31d7de12f6875d9ae11f8e135d2d4c6893aeee7bb6daa5415bafa9f34d43ecc29e7de1667f7adc76ef6d8931953619d5a46c176522f60b1c5ce49d43ca016fedd96dfb02baca94c9828053285ffa5b75bcb13930f0e9827e312f5fb7ad72dd922557ccf708784c516427d3bded8b4a8451db220250f6785a6a59ad3b8af8333830f7c9cafa9ed4dce2dba60630f6811f8f2625932f67311b955a001ed0ab6a16ee300ab6a4',
                'cookie': self.cookies,
            }
            json_data = {
                'variables': {
                    'tweet_text': str(cmt_message),
                    'reply': {
                        'in_reply_to_tweet_id': str(obj_id),
                        'exclude_reply_user_ids': [],
                    },
                    'dark_request': False,
                    'media': {
                        'media_entities': [],
                        'possibly_sensitive': False,
                    },
                    'semantic_annotation_ids': [],
                    'disallowed_reply_options': None,
                },
                'features': {
                    'premium_content_api_read_enabled': False,
                    'communities_web_enable_tweet_community_results_fetch': True,
                    'c9s_tweet_anatomy_moderator_badge_enabled': True,
                    'responsive_web_grok_analyze_button_fetch_trends_enabled': False,
                    'responsive_web_grok_analyze_post_followups_enabled': True,
                    'responsive_web_jetfuel_frame': True,
                    'responsive_web_grok_share_attachment_enabled': True,
                    'responsive_web_edit_tweet_api_enabled': True,
                    'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                    'view_counts_everywhere_api_enabled': True,
                    'longform_notetweets_consumption_enabled': True,
                    'responsive_web_twitter_article_tweet_consumption_enabled': True,
                    'tweet_awards_web_tipping_enabled': False,
                    'responsive_web_grok_show_grok_translated_post': False,
                    'responsive_web_grok_analysis_button_from_backend': True,
                    'creator_subscriptions_quote_tweet_preview_enabled': False,
                    'longform_notetweets_rich_text_read_enabled': True,
                    'longform_notetweets_inline_media_enabled': True,
                    'payments_enabled': False,
                    'profile_label_improvements_pcf_label_in_post_enabled': True,
                    'rweb_tipjar_consumption_enabled': True,
                    'verified_phone_label_enabled': False,
                    'articles_preview_enabled': True,
                    'responsive_web_grok_community_note_auto_translation_is_enabled': False,
                    'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                    'freedom_of_speech_not_reach_fetch_enabled': True,
                    'standardized_nudges_misinfo': True,
                    'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                    'responsive_web_grok_image_annotation_enabled': True,
                    'responsive_web_graphql_timeline_navigation_enabled': True,
                    'responsive_web_enhance_cards_enabled': False,
                },
                'queryId': 'F7hteriqzdRzvMfXM6Ul4w',
            }
            response = requests.post('https://x.com/i/api/graphql/F7hteriqzdRzvMfXM6Ul4w/CreateTweet', headers=headers, json=json_data)
            if response.status_code == 200:
                return True
            else:
                return False
        except:
            return False


# ==================== CLASS THREADS ====================
class Thread():
    def __init__(self, cookies):
        self.cookies = cookies

    def GETDATA(self):
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'cache-control': 'no-cache',
            'dnt': '1',
            'dpr': '1.25',
            'pragma': 'no-cache',
            'priority': 'u=0, i',
            'referer': 'https://www.threads.com/onboarding/',
            'sec-ch-prefers-color-scheme': 'dark',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.49", "Google Chrome";v="138.0.7204.49"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-model': '"Pixel 2"',
            'sec-ch-ua-platform': '"Android"',
            'sec-ch-ua-platform-version': '"8.0"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': user_agent.random,
            'viewport-width': '374',
            'cookie': self.cookies,
        }
        try:
            req = requests.get("https://www.threads.com/", headers=headers, impersonate="chrome120")
            if req.status_code == 200:
                av = str(re.findall('"userID":".*?"', req.text)).split('"userID":"')[1].split('"')[0]
                dtsg = str(re.findall('DTSGInitData.*?token.*?,', req.text)).split('"token":"')[1].split(",")[0]
                match = re.search(r'"LSD"\s*,\s*\[\s*],\s*\{"token"\s*:\s*"([^"]+)"', req.text)
                lsd_token = match.group(1)
                return av, dtsg, lsd_token
            else:
                return False
        except:
            return False

    def GETID__(self, link, TYPE_JOB):
        try:
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
                'cache-control': 'no-cache',
                'dnt': '1',
                'dpr': '1.25',
                'pragma': 'no-cache',
                'priority': 'u=0, i',
                'referer': 'https://www.threads.com/onboarding/',
                'sec-ch-prefers-color-scheme': 'dark',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.49", "Google Chrome";v="138.0.7204.49"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-model': '"Pixel 2"',
                'sec-ch-ua-platform': '"Android"',
                'sec-ch-ua-platform-version': '"8.0"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': user_agent.random,
                'viewport-width': '374',
                'cookie': self.cookies,
            }
            req = requests.get(link, headers=headers)
            if req.status_code == 200:
                if TYPE_JOB == "like":
                    match = re.search(r'"postID"\s*:\s*"(\d+)"', req.text)
                    if match:
                        post_id = match.group(1)
                        return post_id
                    else:
                        return False
                elif TYPE_JOB == "follow":
                    user_ids = re.findall(r'"userID"\s*:\s*"(\d+)"', req.text)
                    return user_ids[0] if user_ids else False
                else:
                    return False
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def LIKE(self, av, dtsg, mediaID, lsd_token):
        try:
            csrftoken = self.cookies.split("csrftoken=")[1].split(";")[0]
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'dnt': '1',
                'origin': 'https://www.threads.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://www.threads.com/',
                'sec-ch-prefers-color-scheme': 'dark',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.49", "Google Chrome";v="138.0.7204.49"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-model': '""',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"15.0.0"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent.random,
                'x-asbd-id': '359341',
                'x-csrftoken': csrftoken,
                'x-fb-friendly-name': 'useBarcelonaLikeMutationLikeMutation',
                'x-fb-lsd': lsd_token,
                'x-ig-app-id': '238260118697367',
                'cookie': self.cookies,
            }
            data = {
                'av': av,
                'fb_dtsg': dtsg,
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'useBarcelonaLikeMutationLikeMutation',
                'variables': '{"mediaID":"' + str(mediaID) + '"}',
                'server_timestamps': 'true',
                'doc_id': '10095211437184657',
            }
            response = requests.post("https://www.threads.com/api/graphql", headers=headers, data=data, impersonate="chrome120")
            if response.status_code == 200:
                if response.json()['data']['record']['media']['has_liked'] == True and response.json()['extensions']['is_final'] == True:
                    return True
            else:
                return False
        except:
            return False

    def Follow(self, av, dtsg, userID, lsd_token):
        try:
            csrftoken = self.cookies.split("csrftoken=")[1].split(";")[0]
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'dnt': '1',
                'origin': 'https://www.threads.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://www.threads.com/@quertynoip',
                'sec-ch-prefers-color-scheme': 'dark',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.49", "Google Chrome";v="138.0.7204.49"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-model': '""',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"15.0.0"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent.random,
                'x-asbd-id': '359341',
                'x-bloks-version-id': 'e4f12b62f425c97b6a785c27bcb08f35b3bf4ff77ba17a7eed5e5116ce52ee4e',
                'x-csrftoken': csrftoken,
                'x-fb-friendly-name': 'useBarcelonaFollowMutationFollowMutation',
                'x-fb-lsd': lsd_token,
                'x-ig-app-id': '238260118697367',
                'x-root-field-name': 'xdt_text_app_follow_user',
                'cookie': self.cookies
            }
            data = {
                'av': av,
                'fb_dtsg': dtsg,
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'useBarcelonaFollowMutationFollowMutation',
                'variables': '{"target_user_id":"' + userID + '","media_id_attribution":null,"container_module":"ig_text_feed_profile"}',
                'server_timestamps': 'true',
                'doc_id': '9600795776704785',
            }
            response = requests.post('https://www.threads.com/graphql/query', headers=headers, data=data, impersonate="chrome120")
            if response.status_code == 200:
                if response.json()['data']['data']['user']['friendship_status']['following'] == True and response.json()['extensions']['is_final'] == True and response.json()['status'] == "ok":
                    return True
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False


# ==================== CLASS PINTEREST ====================
class Pinterest():
    def __init__(self, cookies):
        self.cookies = cookies

    def GETDATA(self):
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'cache-control': 'no-cache',
            'dnt': '1',
            'pragma': 'no-cache',
            'priority': 'u=0, i',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.101", "Google Chrome";v="138.0.7204.101"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'service-worker-navigation-preload': 'true',
            'upgrade-insecure-requests': '1',
            'user-agent': user_agent.random,
            'cookie': self.cookies,
        }
        try:
            response = requests.get('https://www.pinterest.com/settings', headers=headers, impersonate="chrome120")
            if response.status_code == 200:
                match = re.search(r'"client_span_id"\s*:\s*"([^"]+)"', response.text)
                if match:
                    client_span_id = match.group(1)
                else:
                    return False
                match2 = re.search(r'"trace_id"\s*:\s*"([^"]+)"', response.text)
                if match2:
                    trace_id = match.group(1)
                else:
                    return False
                match3 = re.search(r'"username"\s*:\s*"([^"]+)"', response.text)
                if match3:
                    last_name = match3.group(1)
                else:
                    return False
                return client_span_id, trace_id, last_name
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def follow(self, spanid, trace_id, targetID, linkjob):
        try:
            match = re.search(r'/[^/]+/', linkjob)
            if match:
                source_url = match.group()
            else:
                return False
            headers = {
                'accept': 'application/json, text/javascript, */*, q=0.01',
                'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
                'cache-control': 'no-cache',
                'content-type': 'application/x-www-form-urlencoded',
                'dnt': '1',
                'origin': 'https://www.pinterest.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://www.pinterest.com/',
                'screen-dpr': '1.25',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-full-version-list': '"Not)A;Brand";v="8.0.0.0", "Chromium";v="138.0.7204.101", "Google Chrome";v="138.0.7204.101"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-model': '""',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"15.0.0"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent.random,
                'x-app-version': 'a349e61',
                'x-b3-flags': '0',
                'x-b3-parentspanid': '2bb7968aab05e5f8',
                'x-b3-spanid': spanid,
                'x-b3-traceid': trace_id,
                'x-csrftoken': self.cookies.split("csrftoken=")[1].split(";")[0] if "csrftoken=" in self.cookies else "0",
                'x-pinterest-appstate': 'active',
                'x-pinterest-pws-handler': 'www/[username].js',
                'x-pinterest-source-url': source_url,
                'x-requested-with': 'XMLHttpRequest',
                'cookie': self.cookies
            }
            data = {
                'source_url': source_url,
                'data': '{"options":{"user_id":"' + targetID + '"},"context":{}}',
            }
            response = requests.post('https://www.pinterest.com/resource/UserFollowResource/create/', headers=headers, data=data, impersonate="chrome120")
            if response.status_code == 200:
                if response.json()['resource_response']['status'] == "success" and response.json()['resource_response']['message'] == "ok":
                    return True
                else:
                    return False
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False


# ==================== CLASS LINKEDIN ====================
class Linkedin():
    def __init__(self, cookies):
        self.cookies = cookies

    def GETDATA(self):
        try:
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'dnt': '1',
                'pragma': 'no-cache',
                'priority': 'u=0, i',
                'referer': 'https://www.linkedin.com/',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': user_agent.random,
                'cookie': self.cookies,
            }
            response = requests.get('https://www.linkedin.com/feed/', headers=headers, impersonate="chrome120", allow_redirects=False)
            if response.status_code == 200:
                return True
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def GETID(self, url):
        type = 'company' if 'company' in url else 'profile'
        try:
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'dnt': '1',
                'pragma': 'no-cache',
                'priority': 'u=0, i',
                'referer': 'https://www.linkedin.com/uas/login-submit',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': user_agent.random,
                'cookie': self.cookies
            }
            res = requests.get(url, headers=headers, impersonate="chrome120")
            if res.status_code == 200:
                match = re.findall('urn:li:fsd_profileCard:\\(([^,]+),', res.text) if type == "profile" in res.text else re.findall('urn:li:fsd_company:([A-Za-z0-9]+)', res.text)
                ID = match[0]
                return ID, type
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def follow(self, ID, type):
        try:
            csrf_token = self.cookies.split('JSESSIONID=')[1].split(';')[0]
            if '"' in csrf_token:
                csrf_token = csrf_token.replace('"', '')
            instance = "urn:li:page:d_flagship3_company" if type == "company" else "urn:li:page:d_flagship3_profile"
            metadata = "Voyager - Follows=follow-action,Voyager - Profile Actions=topcard-primary-follow-action-click" if type == "company" else "Voyager - Follows=follow-action,Voyager - Profile Actions=topcard-primary-follow-action-click"
            headers = {
                'accept': 'application/vnd.linkedin.normalized+json+2.1',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/json; charset=UTF-8',
                'csrf-token': csrf_token,
                'dnt': '1',
                'origin': 'https://www.linkedin.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://www.linkedin.com/in/anis-hassen/',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': user_agent.random,
                'x-li-lang': 'en_US',
                'x-li-page-instance': instance,
                'x-li-pem-metadata': metadata,
                'x-li-track': '{"clientVersion":"1.13.36800.3","mpVersion":"1.13.36800.3","osName":"web","timezoneOffset":7,"timezone":"Asia/Bangkok","deviceFormFactor":"DESKTOP","mpName":"voyager-web","displayDensity":1.5625,"displayWidth":2400,"displayHeight":1350}',
                'x-restli-protocol-version': '2.0.0',
                'cookie': self.cookies,
            }
            url = "https://www.linkedin.com/voyager/api/feed/dash/followingStates/urn:li:fsd_followingState:urn:li:fsd_profile:" + ID if type == "profile" else "https://www.linkedin.com/voyager/api/feed/dash/followingStates/urn:li:fsd_followingState:urn:li:fsd_company:" + ID if type == "company" else False
            json_data = {
                'patch': {
                    '$set': {
                        'following': True,
                    },
                },
            }
            response = requests.post(url, json=json_data, headers=headers, impersonate="chrome120")
            if response.status_code == 201:
                return True
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def Like(self, ID):
        try:
            csrf_token = self.cookies.split('JSESSIONID=')[1].split(';')[0]
            if '"' in csrf_token:
                csrf_token = csrf_token.replace('"', '')
            headers = {
                'accept': 'application/vnd.linkedin.normalized+json+2.1',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'content-type': 'application/json; charset=UTF-8',
                'csrf-token': csrf_token,
                'dnt': '1',
                'origin': 'https://www.linkedin.com',
                'pragma': 'no-cache',
                'priority': 'u=1, i',
                'referer': 'https://www.linkedin.com/posts/unjobsandngojobs_ivf-opportunitiescorners-turkey-activity-7345051810350465024-ozad/?utm_source=share&utm_medium=member_desktop&rcm=ACoAAFw4MC4BQo7BlZhvEpPGa0IAS5l7OnIlKQ8',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                'x-li-lang': 'en_US',
                'x-li-page-instance': 'urn:li:page:d_flagship3_detail_base',
                'x-li-track': '{"clientVersion":"1.13.36800.3","mpVersion":"1.13.36800.3","osName":"web","timezoneOffset":7,"timezone":"Asia/Bangkok","deviceFormFactor":"DESKTOP","mpName":"voyager-web","displayDensity":1.5625,"displayWidth":2400,"displayHeight":1350}',
                'x-restli-protocol-version': '2.0.0',
                'cookie': self.cookies,
            }
            params = {
                'action': 'execute',
                'queryId': 'voyagerSocialDashReactions.b731222600772fd42464c0fe19bd722b',
            }
            json_data = {
                'variables': {
                    'entity': {
                        'reactionType': 'LIKE',
                    },
                    'threadUrn': f'urn:li:activity:{ID}',
                },
                'queryId': 'voyagerSocialDashReactions.b731222600772fd42464c0fe19bd722b',
                'includeWebMetadata': True,
            }
            response = requests.post('https://www.linkedin.com/voyager/api/graphql', params=params, headers=headers, json=json_data, impersonate="chrome120")
            if response.status_code == 200:
                return True
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False


# ==================== CLASS BLUESKY ====================
class BlueSky():
    def __init__(self, authorization):
        self.authorization = authorization
        self.header = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'atproto-accept-labelers': 'did:plc:ar7c4by46qjdydhdevvrndac;redact',
            'atproto-proxy': 'did:web:api.bsky.app#bsky_appview',
            'authorization': self.authorization,
            'cache-control': 'no-cache',
            'dnt': '1',
            'origin': 'https://bsky.app',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://bsky.app/',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Linux; Android 8.0; Pixel 2 Build/OPD3.170816.012) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        }

    def GETDATA(self):
        r = std_requests.get('https://auriporia.us-west.host.bsky.network/xrpc/com.atproto.server.getSession', headers=self.header)
        try:
            if r.status_code == 200:
                return r.json()
            else:
                return False
        except:
            return False

    def Follow(self, url):
        self.did = BlueSky(self.authorization).GETDATA()
        if not self.did:
            return False
        r = std_requests.get(url, headers=self.header)
        if r.status_code == 200:
            data = re.findall('bsky_did">.*?<', r.text)
            if data:
                bsky_did = data[0].split("plc:")[1].split('<')[0]
                json_data = {
                    'collection': 'app.bsky.graph.follow',
                    'repo': self.did['did'],
                    'record': {
                        'subject': f'did:plc:{bsky_did}',
                        'createdAt': '2025-09-07T14:26:12.525Z',
                        '$type': 'app.bsky.graph.follow',
                    },
                }
                response = std_requests.post("https://auriporia.us-west.host.bsky.network/xrpc/com.atproto.repo.createRecord", json=json_data, headers=self.header)
                if response.status_code == 200:
                    if response.json()['validationStatus'] == "valid":
                        return True
                    else:
                        return False
                else:
                    return False
            else:
                return False
        else:
            return False


# ==================== CLASS YOUTUBE ====================
class YouTube():
    def __init__(self, cookies):
        self.cookies = cookies

    def _make_client_nonce(self, length=16):
        chars = string.ascii_letters + string.digits + "-_"
        return "".join(random.choice(chars) for _ in range(length))

    def _decode_b64(self, s):
        s = s.replace("%3D", "=")
        return base64.urlsafe_b64decode(s)

    def _get_sapisidhash(self, origin="https://www.youtube.com"):
        sapisid = None
        for p in self.cookies.split(";"):
            p = p.strip()
            if p.startswith("__Secure-3PAPISID="):
                sapisid = p.split("=", 1)[1]
                break
            elif p.startswith("SAPISID="):
                sapisid = p.split("=", 1)[1]
                break
        if not sapisid:
            return False
        timestamp = int(time.time())
        to_hash = f"{timestamp} {sapisid} {origin}"
        sha1_hash = hashlib.sha1(to_hash.encode("utf-8")).hexdigest()
        return f"SAPISIDHASH {timestamp}_{sha1_hash}"

    def GETDATA(self):
        headers = {
            'accept': '*/*',
            'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
            'authorization': self._get_sapisidhash(),
            'content-type': 'application/json',
            'origin': 'https://www.youtube.com',
            'priority': 'u=1, i',
            'referer': 'https://www.youtube.com/@nhacnghetrenbar.',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-form-factors': '"Desktop"',
            'sec-ch-ua-full-version': '"139.0.7258.157"',
            'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.157", "Chromium";v="139.0.7258.157"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-ch-ua-wow64': '?0',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'same-origin',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'x-browser-channel': 'stable',
            'x-browser-copyright': 'Copyright 2025 Google LLC. All rights reserved.',
            'x-browser-validation': 'XPdmRdCCj2OkELQ2uovjJFk6aKA=',
            'x-browser-year': '2025',
            'x-client-data': 'CJW2yQEIpbbJAQipncoBCLyKywEIlKHLAQjNo8sBCIWgzQEIk4HPAQjuhM8BCLWFzwEIz4XPAQiAiM8BGOntzgEYzYLPARjYhs8B',
            'x-goog-authuser': '0',
            'x-goog-visitor-id': 'Cgt5dXpraW1JNGpwbyj71urFBjIKCgJWThIEGgAgXw%3D%3D',
            'x-origin': 'https://www.youtube.com',
            'x-youtube-bootstrap-logged-in': 'true',
            'x-youtube-client-name': '1',
            'x-youtube-client-version': '2.20250904.01.00',
            'cookie': self.cookies,
        }
        data = std_requests.get("https://www.youtube.com/", headers=headers)
        if data.status_code == 200:
            match = re.search(r'"USER_ACCOUNT_NAME"\s*:\s*"([^"]+)"', data.text)
            if match:
                return True
            else:
                return False
        else:
            return False

    def _update_cookies(self, response):
        cookies_dict = {}
        for part in self.cookies.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies_dict[k.strip()] = v.strip()
        for c in response.cookies:
            cookies_dict[c.name] = c.value
        return "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])

    def Rotate_cookies(self):
        if self._get_sapisidhash() == False:
            return False
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
            'priority': 'u=0, i',
            'referer': 'https://www.youtube.com/',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-form-factors': '"Desktop"',
            'sec-ch-ua-full-version': '"139.0.7258.157"',
            'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.157", "Chromium";v="139.0.7258.157"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-ch-ua-wow64': '?0',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-site',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'x-browser-channel': 'stable',
            'x-browser-copyright': 'Copyright 2025 Google LLC. All rights reserved.',
            'x-browser-validation': 'XPdmRdCCj2OkELQ2uovjJFk6aKA=',
            'x-browser-year': '2025',
            'x-client-data': 'CJW2yQEIpbbJAQipncoBCLyKywEIlaHLAQiFoM0BCO6EzwEIz4XPAQiAiM8BCIaKzwE=',
            'cookie': self.cookies,
        }
        try:
            r = std_requests.get("https://accounts.youtube.com/RotateCookiesPage?origin=https://www.youtube.com&yt_pid=1", headers=headers)
            if r.status_code == 200:
                pattern = r"init\('(-?\d+)'"
                match = re.search(pattern, r.text)
                if match:
                    init = match.group(1)
                else:
                    return False
            else:
                return False
        except:
            return False

        headers2 = {
            'accept': '*/*',
            'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
            'content-type': 'application/json',
            'origin': 'https://accounts.youtube.com',
            'priority': 'u=1, i',
            'referer': 'https://accounts.youtube.com/RotateCookiesPage?origin=https://www.youtube.com&yt_pid=1',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-form-factors': '"Desktop"',
            'sec-ch-ua-full-version': '"139.0.7258.157"',
            'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.157", "Chromium";v="139.0.7258.157"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-ch-ua-wow64': '?0',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'same-origin',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'x-browser-channel': 'stable',
            'x-browser-copyright': 'Copyright 2025 Google LLC. All rights reserved.',
            'x-browser-validation': 'XPdmRdCCj2OkELQ2uovjJFk6aKA=',
            'x-browser-year': '2025',
            'x-client-data': 'CJW2yQEIpbbJAQipncoBCLyKywEIlaHLAQiFoM0BCJKBzwEI7oTPAQjPhc8BCICIzwEIhorPARjp7c4B',
            'cookie': self.cookies
        }
        json_data = [None, str(init), 1]
        try:
            response = std_requests.post('https://accounts.youtube.com/RotateCookies', headers=headers2, json=json_data)
            if response.status_code == 200:
                merged_cookie = self._update_cookies(response)
                return merged_cookie
            else:
                return False
        except:
            return False

    def SUB(self, url):
        if self._get_sapisidhash() == False:
            return False
        try:
            headers = {
                'accept': '*/*',
                'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
                'authorization': self._get_sapisidhash(),
                'content-type': 'application/json',
                'origin': 'https://www.youtube.com',
                'priority': 'u=1, i',
                'referer': 'https://www.youtube.com/@nhacnghetrenbar.',
                'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                'sec-ch-ua-arch': '"x86"',
                'sec-ch-ua-bitness': '"64"',
                'sec-ch-ua-form-factors': '"Desktop"',
                'sec-ch-ua-full-version': '"139.0.7258.157"',
                'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.157", "Chromium";v="139.0.7258.157"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-model': '""',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"15.0.0"',
                'sec-ch-ua-wow64': '?0',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'same-origin',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
                'x-browser-channel': 'stable',
                'x-browser-copyright': 'Copyright 2025 Google LLC. All rights reserved.',
                'x-browser-validation': 'XPdmRdCCj2OkELQ2uovjJFk6aKA=',
                'x-browser-year': '2025',
                'x-client-data': 'CJW2yQEIpbbJAQipncoBCLyKywEIlKHLAQjNo8sBCIWgzQEIk4HPAQjuhM8BCLWFzwEIz4XPAQiAiM8BGOntzgEYzYLPARjYhs8B',
                'x-goog-authuser': '0',
                'x-goog-visitor-id': 'Cgt5dXpraW1JNGpwbyj71urFBjIKCgJWThIEGgAgXw%3D%3D',
                'x-origin': 'https://www.youtube.com',
                'x-youtube-bootstrap-logged-in': 'true',
                'x-youtube-client-name': '1',
                'x-youtube-client-version': '2.20250904.01.00',
                'cookie': self.cookies,
            }
            data = std_requests.get(url, headers=headers).text
            clickTrackingParams_raw = r'"buttonText":"Subscribe".*?"clickTrackingParams":"([^"]+)"'
            clickTrackingParam = re.findall(clickTrackingParams_raw, data, flags=re.DOTALL)
            channelIds_raw = r'"channelIds"\s*:\s*\[\s*"([^"]+)"\s*\]'
            channelIds = re.findall(channelIds_raw, data)
            if not channelIds:
                return False
            params = {'prettyPrint': 'false'}
            json_data = {
                'context': {
                    'client': {
                        'hl': 'en',
                        'gl': 'VN',
                        'remoteHost': '2401:d800:5296:239d:5db:e7a2:97a0:9d70',
                        'visitorData': 'Cgt5dXpraW1JNGpwbyjs2OvFBjIKCgJWThIEGgAgXw%3D%3D',
                        'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36,gzip(gfe)',
                        'clientName': 'WEB',
                        'clientVersion': '2.20250904.01.00',
                        'osName': 'Windows',
                        'osVersion': '10.0',
                        'originalUrl': url,
                        'platform': 'DESKTOP',
                        'userInterfaceTheme': 'USER_INTERFACE_THEME_DARK',
                        'timeZone': 'Asia/Bangkok',
                        'browserName': 'Chrome',
                        'browserVersion': '139.0.0.0',
                        'acceptHeader': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'utcOffsetMinutes': 420,
                        'mainAppWebInfo': {
                            'graftUrl': url,
                            'webDisplayMode': 'WEB_DISPLAY_MODE_BROWSER',
                            'isWebNativeShareAvailable': True,
                        },
                    },
                    'user': {'lockedSafetyMode': False},
                    'request': {'useSsl': True, 'internalExperimentFlags': [], 'consistencyTokenJars': []},
                    'clientScreenNonce': self._make_client_nonce(),
                    'clickTracking': {'clickTrackingParams': clickTrackingParam[0] if clickTrackingParam else ""},
                },
                'channelIds': [channelIds[0]],
                'params': 'EgIIAhgA',
            }
            response = std_requests.post('https://www.youtube.com/youtubei/v1/subscription/subscribe', params=params, headers=headers, json=json_data)
            if response.status_code == 200:
                return True
            else:
                return False
        except:
            return False

    def CMT(self, url, cmt):
        if self._get_sapisidhash() == False:
            return False
        headers = {
            'accept': '*/*',
            'accept-language': 'vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5',
            'authorization': self._get_sapisidhash(),
            'content-type': 'application/json',
            'origin': 'https://www.youtube.com',
            'priority': 'u=1, i',
            'referer': 'https://www.youtube.com/watch?v=cuMe7_apgBQ&list=RDcuMe7_apgBQ&start_radio=1',
            'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-form-factors': '"Desktop"',
            'sec-ch-ua-full-version': '"139.0.7258.157"',
            'sec-ch-ua-full-version-list': '"Not;A=Brand";v="99.0.0.0", "Google Chrome";v="139.0.7258.157", "Chromium";v="139.0.7258.157"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-model': '""',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"15.0.0"',
            'sec-ch-ua-wow64': '?0',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'same-origin',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
            'x-browser-channel': 'stable',
            'x-browser-copyright': 'Copyright 2025 Google LLC. All rights reserved.',
            'x-browser-validation': 'XPdmRdCCj2OkELQ2uovjJFk6aKA=',
            'x-browser-year': '2025',
            'x-client-data': 'CJW2yQEIpbbJAQipncoBCLyKywEIk6HLAQiFoM0BCO6EzwEIz4XPAQiAiM8BCIaKzwEY6e3OAQ==',
            'x-goog-authuser': '0',
            'x-goog-visitor-id': 'Cgt5dXpraW1JNGpwbyiC_o_GBjIKCgJWThIEGgAgXw%3D%3D',
            'x-origin': 'https://www.youtube.com',
            'x-youtube-bootstrap-logged-in': 'true',
            'x-youtube-client-name': '1',
            'x-youtube-client-version': '2.20250910.00.00',
            'cookie': self.cookies,
        }
        data = std_requests.get(url, headers=headers).text
        section_match = re.search(r'"sectionIdentifier":"comment-item-section".{0,5000}', data)
        if not section_match:
            return False
        section_text = section_match.group(0)
        match = re.search(r'"clickTrackingParams"\s*:\s*"([^"]+)"', section_text)
        if match:
            clickTrackingParams = match.group(1)
        else:
            return False
        pattern = r'(?:clickTrackingParams|trackingParams)"\s*:\s*"(?P<token>CM[^"]*?)"'
        matches2 = re.findall(pattern, data)
        if matches2:
            tokens2 = [item for item in matches2 if item.startswith("CM")]
        else:
            return False
        pattern_continuation = r'"continuationCommand":\{"token":"([^"]+)"'
        continuation_matches = re.findall(pattern_continuation, data)
        if continuation_matches:
            token = continuation_matches[0]
        else:
            return False
        params = {'prettyPrint': 'false'}
        json_data = {
            'context': {
                'client': {
                    'hl': 'en',
                    'gl': 'VN',
                    'visitorData': 'Cgt5dXpraW1JNGpwbyjT1ZDGBjIKCgJWThIEGgAgXw%3D%3D',
                    'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36,gzip(gfe)',
                    'clientName': 'WEB',
                    'clientVersion': '2.20250910.00.00',
                    'osName': 'Windows',
                    'osVersion': '10.0',
                    'originalUrl': url,
                    'platform': 'DESKTOP',
                    'userInterfaceTheme': 'USER_INTERFACE_THEME_DARK',
                    'timeZone': 'Asia/Bangkok',
                    'browserName': 'Chrome',
                    'browserVersion': '139.0.0.0',
                    'acceptHeader': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'utcOffsetMinutes': 420,
                    'mainAppWebInfo': {
                        'graftUrl': url,
                        'webDisplayMode': 'WEB_DISPLAY_MODE_BROWSER',
                        'isWebNativeShareAvailable': True,
                    },
                },
                'user': {'lockedSafetyMode': False},
                'request': {'useSsl': True, 'internalExperimentFlags': [], 'consistencyTokenJars': []},
                'clickTracking': {'clickTrackingParams': tokens2[0] if tokens2 else ""},
            },
            'continuation': token,
        }
        try:
            response = std_requests.post('https://www.youtube.com/youtubei/v1/next', params=params, headers=headers, json=json_data)
            pattern_cmt = r'"createCommentParams"\s*:\s*"([^"]+)"'
            match3 = re.search(pattern_cmt, response.text)
            if match3:
                createCommentParams = match3.group(1)
            else:
                return False
        except:
            return False

        json_data2 = {
            'context': {
                'client': {
                    'hl': 'en',
                    'gl': 'VN',
                    'visitorData': 'Cgt5dXpraW1JNGpwbyiC_o_GBjIKCgJWThIEGgAgXw%3D%3D',
                    'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36,gzip(gfe)',
                    'clientName': 'WEB',
                    'clientVersion': '2.20250910.00.00',
                    'osName': 'Windows',
                    'osVersion': '10.0',
                    'originalUrl': url,
                    'platform': 'DESKTOP',
                    'userInterfaceTheme': 'USER_INTERFACE_THEME_DARK',
                    'timeZone': 'Asia/Bangkok',
                    'browserName': 'Chrome',
                    'browserVersion': '139.0.0.0',
                    'acceptHeader': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'utcOffsetMinutes': 420,
                    'mainAppWebInfo': {
                        'graftUrl': url,
                        'webDisplayMode': 'WEB_DISPLAY_MODE_BROWSER',
                        'isWebNativeShareAvailable': True,
                    },
                },
                'user': {'lockedSafetyMode': False},
                'request': {'useSsl': True, 'internalExperimentFlags': [], 'consistencyTokenJars': []},
                'clientScreenNonce': self._make_client_nonce(),
                'clickTracking': {'clickTrackingParams': clickTrackingParams},
            },
            'createCommentParams': createCommentParams,
            'commentText': cmt,
        }
        try:
            response = std_requests.post('https://www.youtube.com/youtubei/v1/comment/create_comment', params=params, headers=headers, json=json_data2)
            if response.status_code == 200:
                return True
            else:
                return False
        except:
            return False


# ==================== CLASS GOLIKE ====================
class GOLIKE():
    def __init__(self, authorization):
        self.authorization = authorization
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9,vi-VN;q=0.8,vi;q=0.7',
            'authorization': authorization,
            'cache-control': 'no-cache',
            'content-type': 'application/json;charset=utf-8',
            'dnt': '1',
            'origin': 'https://app.golike.net',
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            't': 'VFZSak1VMVVRWHBOZW1zeFRVRTlQUT09',
            'user-agent': user_agent.random,
        }

    def GET_USER(self):
        url = "https://gateway.golike.net/api/users/me"
        try:
            res = requests.get(url, headers=self.headers, impersonate="safari_ios")
            if res.status_code == 200:
                return res.json()
            else:
                return False
        except:
            return False

    def GET_ACC(self, account_type, username_type):
        username = []
        id = []
        nickname = []
        url = f"https://gateway.golike.net/api/{account_type}-account"
        try:
            res = requests.get(url, headers=self.headers, impersonate="safari_ios")
            if res.status_code == 200:
                for i in res.json()['data']:
                    username.append(i[username_type])
                    id.append(i['id'])
                    if account_type == 'tiktok':
                        nickname.append(i['unique_username'])
                if account_type == 'tiktok':
                    return username, id, nickname
                else:
                    return username, id
            else:
                return False
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            return False

    def GETJOB(self, job_type, account_id, account_type):
        url = f"https://gateway.golike.net/api/advertising/publishers/{job_type}/jobs?{account_type}=" + \
              str(account_id) + "&data=null"
        try:
            res = requests.get(url, headers=self.headers, impersonate="safari_ios")
            return res.json()
        except:
            return False

    def HT(self, account_id, ads_id, JOB_TYPE):
        try:
            json_data = {
                'account_id': account_id,
                'ads_id': ads_id,
                'async': True,
                'data': None,
            } if JOB_TYPE != "instagram" else {
                'instagram_users_advertising_id': ads_id,
                'instagram_account_id': account_id,
                'async': True,
                'data': None,
            }
            response = requests.post(f'https://gateway.golike.net/api/advertising/publishers/{JOB_TYPE}/complete-jobs',
                                     headers=self.headers, json=json_data, impersonate="safari_ios")
            return response.json()
        except:
            return False

    def HT2(self, account_id, ads_id, comment_id, message, JOB_TYPE):
        try:
            json_data = {
                'instagram_users_advertising_id': ads_id,
                'instagram_account_id': account_id,
                'async': True,
                'data': None,
                'comment_id': comment_id,
                'message': message,
            }
            response = requests.post(f'https://gateway.golike.net/api/advertising/publishers/{JOB_TYPE}/complete-jobs',
                                     headers=self.headers, json=json_data, impersonate="safari_ios")
            return response.json()
        except:
            return False

    def skip_JOB(self, ads_id, object_id, account_id, type, JOB_TYPE):
        try:
            json_data = {
                'ads_id': ads_id,
                'object_id': str(object_id),
                'account_id': account_id,
                'type': type,
            }
            response = requests.post(f'https://gateway.golike.net/api/advertising/publishers/{JOB_TYPE}/skip-jobs',
                                     headers=self.headers, json=json_data, impersonate="safari_ios")
            if response.status_code == 200:
                return response.json()
        except:
            return False

    def HT3(self, ads_id, account_id, comment_id, message):
        try:
            json_data = {
                'ads_id': ads_id,
                'account_id': account_id,
                'async': True,
                'data': None,
                'comment_id': comment_id,
                'message': message,
            }
            response = requests.post('https://gateway.golike.net/api/advertising/publishers/youtube/complete-jobs',
                                     headers=self.headers, json=json_data, impersonate="safari_ios")
            if response.status_code == 200:
                return response.json()
        except:
            return False


# ==================== FUNCTIONS FOR YOUTUBE (URL handling) ====================
def yt_get_url(url):
    if '?' in url:
        return url.split("?")[0]
    else:
        return url


# ==================== CONFIG MANAGEMENT ====================
def LoadJSON():
    filepath = "config/config.json"
    default_data = {
        "data": {
            "Auth": "",
            "MXH": {
                "TikTok": {},
                "INSTAGRAM": {"auth": {}},
                "THREADS": {"auth": {}},
                "LINKEDIN": {"auth": {}},
                "PINTEREST": {"auth": {}},
                "YOUTUBE": {"auth": {}},
                "BLUESKY": {"auth": {}}
            },
            "copyright": "DENO9099",
            "VERSION": "v1.0.22"
        }
    }
    if not os.path.exists("config"):
        os.makedirs("config")
    if not os.path.isfile(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4, ensure_ascii=False)
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def SaveJSON(config):
    with open("config/config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def ADD_COOKIES(MXH, id, cookies):
    data = LoadJSON()
    if MXH not in data['data']['MXH']:
        data['data']['MXH'][MXH] = {"auth": {}}
    data['data']['MXH'][MXH]['auth'][id] = cookies
    SaveJSON(data)


def check_cookies(MXH, id):
    data = LoadJSON()
    try:
        cookies = data['data']['MXH'][MXH]['auth']
        return bool(cookies.get(id))
    except KeyError:
        return False


# ==================== UI FUNCTIONS ====================
class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    LIGHT_CYAN = '\033[96m'
    LIGHT_PURPLE = '\033[95m'
    LIGHT_GREEN = '\033[92m'
    LIGHT_RED = '\033[91m'
    LIGHT_WHITE = '\033[97m'
    END = '\033[0m'


def ascii_img():
    print("""\033[38;2;153;51;255m▄▄▄█████▓ █    ██   ██████    ▄▄▄█████▓ ▒█████   ▒█████   ██▓\033[0m
\033[38;2;170;70;255m▓  ██▒ ▓▒ ██  ▓██▒▒██    ▒    ▓  ██▒ ▓▒▒██▒  ██▒▒██▒  ██▒▓██▒\033[0m
\033[38;2;190;90;255m▒ ▓██░ ▒░▓██  ▒██░░ ▓██▄      ▒ ▓██░ ▒░▒██░  ██▒▒██░  ██▒▒██░\033[0m
\033[38;2;210;110;240m░ ▓██▓ ░ ▓▓█  ░██░  ▒   ██▒   ░ ▓██▓ ░ ▒██   ██░▒██   ██░▒██░\033[0m
\033[38;2;230;130;220m  ▒██▒ ░ ▒▒█████▓ ▒██████▒▒     ▒██▒ ░ ░ ████▓▒░░ ████▓▒░░██████▒\033[0m
\033[38;2;240;150;200m  ▒ ░░   ░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░     ▒ ░░   ░ ▒░▒░▒░ ░ ▒░▒░▒░ ░ ▒░▓  ░\033[0m
\033[38;2;200;200;255m    ░    ░░▒░ ░ ░ ░ ░▒  ░ ░       ░      ░ ▒ ▒░   ░ ▒ ▒░ ░ ░ ▒  ░\033[0m
\033[38;2;150;230;255m  ░       ░░░ ░ ░ ░  ░  ░       ░      ░ ░ ░ ▒  ░ ░ ░ ▒    ░ ░\033[0m
\033[38;2;120;255;230m            ░           ░                  ░ ░      ░ ░      ░  ░\033[0m

\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mADMIN: NHƯ ANH ĐÃ THẤY EM   \033[38;2;255;220;160mPhiên Bản: \033[38;2;120;255;220mv3.20\033[0m
\033[38;2;255;200;140m[</>] \033[38;2;200;160;255mNhóm Telegram: \033[38;2;120;255;220mhttps://t.me/se_meo_bao_an\033[0m
\033[38;2;190;235;210m───────────────────────────────────────────────────────────────────────\033[0m""") 


def draw_full_width_box_mini(text):
    terminal_width = shutil.get_terminal_size().columns // 3
    text_with_color = Color.YELLOW + text + Color.GREEN
    text_len = len(text)
    padding_total = terminal_width - 2 - text_len
    padding_left = padding_total // 2
    padding_right = padding_total - padding_left
    print(Color.GREEN + "┌" + "─" * (terminal_width - 2) + "┐")
    print("│" + " " * padding_left + text_with_color + " " * padding_right + "│")
    print("└" + "─" * (terminal_width - 2) + "┘" + Color.END)


def draw_full_width_box(text):
    terminal_width = shutil.get_terminal_size().columns
    text_with_color = Color.YELLOW + text + Color.GREEN
    text_len = len(text)
    padding_total = terminal_width - 2 - text_len
    padding_left = padding_total // 2
    padding_right = padding_total - padding_left
    print(Color.GREEN + "┌" + "─" * (terminal_width - 2) + "┐")
    print("│" + " " * padding_left + text_with_color + " " * padding_right + "│")
    print("└" + "─" * (terminal_width - 2) + "┘" + Color.END)


def split_terminal():
    width = os.get_terminal_size().columns
    print("-" * width)


def LOGO_TEXT(text1, text2):
    print(f"{Color.RED}[{Color.END}:D{Color.RED}]{Color.END} => {Color.GREEN} {text1} : {Color.CYAN} {text2} {Color.END}")


def FN_TEXT(int_id, text2):
    print(f"{Color.RED}[{Color.END}θ{Color.RED}]{Color.END}{chr(172)}{Color.GREEN} {Color.YELLOW}{int_id}{Color.END} => {Color.CYAN}{text2}{Color.END}")


def warning_text(text1):
    print(f"{Color.RED}[{Color.END}!{Color.RED}]{Color.END} => {Color.GREEN} {text1} ")


def input_text(text1):
    data = input(f"{Color.RED}[{Color.END}＄{Color.RED}]{Color.END} => {Color.GREEN} {text1} {Color.END}")
    return data


def choose_input(text):
    data = input(f"{Color.RED}[{Color.END}I{Color.RED}]{Color.END} => {Color.GREEN} {text} {Color.END}")
    return data


# ==================== MAIN MENU ====================
def menu_live(info, auth):
    split_terminal()
    LOGO_TEXT("ID Tài Khoản", str(info["data"]["id"]))
    LOGO_TEXT("Tên Người Dùng", str(info["data"]["name"]))
    LOGO_TEXT("Tên Tài Khoản", str(info["data"]["username"]))
    LOGO_TEXT("Số dư", str(info["data"]["coin"]))
    split_terminal()
    draw_full_width_box("THÔNG TIN THIẾT BỊ")
    LOGO_TEXT("Hệ điều hành hành", str(platform.system()))
    try:
        info_ip = std_requests.get("http://ip-api.com/json")
        if info_ip.status_code == 200:
            LOGO_TEXT("IP", str(info_ip.json()['query']))
            LOGO_TEXT("Khu Vực", str(info_ip.json()['regionName']))
            LOGO_TEXT("Isp", str(info_ip.json()['isp']))
            LOGO_TEXT("Nhà Mạng", str(info_ip.json()['org']))
        else:
            LOGO_TEXT("IP", "Không xác định")
            LOGO_TEXT("Khu Vực", "Không xác định")
            LOGO_TEXT("Isp", "Không xác định")
            LOGO_TEXT("Nhà Mạng", "Không xác định")
    except:
        LOGO_TEXT("IP", "Không xác định")
        LOGO_TEXT("Khu Vực", "Không xác định")
        LOGO_TEXT("Isp", "Không xác định")
        LOGO_TEXT("Nhà Mạng", "Không xác định")
    split_terminal()
    draw_full_width_box("CHỨC NĂNG GOLIKE")
    draw_full_width_box_mini("REQUESTS => [PC+MOBILE]")
    FN_TEXT(1, "Chạy Tự Động Instagram")
    FN_TEXT(2, "Chạy Tự Động Threads")
    FN_TEXT(3, "Chạy Tự Động Linkedin")
    FN_TEXT(4, "Chạy Tự Động Pinterest")
    FN_TEXT(16, "Chạy Tự Động Youtube")
    FN_TEXT(17, "Chạy Tự Động BlueSky")
    draw_full_width_box("ĐỔI Authorization")
    FN_TEXT(0, "ĐỔI Authorization")

    while True:
        try:
            CHOOSE = choose_input("NHẬP CHỨC NĂNG CỦA TOOL : ")
            if int(CHOOSE) >= 0 and int(CHOOSE) <= 17:
                break
        except KeyboardInterrupt:
            sys.exit(0)
        except:
            pass

    # Xử lý các chức năng
    if CHOOSE == "0":
        data = LoadJSON()
        data['data']['Auth'] = ""
        SaveJSON(data)
        main()
    elif CHOOSE == "1":
        # Instagram
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("THÔNG TIN TÀI KHOẢN")
        account = GOLIKE(auth).GET_ACC("instagram", "instagram_username")
        if len(account[0]) == 0:
            warning_text("KHÔNG CÓ TÀI KHOẢN ! VUI LÒNG VÀO GOLIKE ĐỂ THÊM TÀI KHOẢN")
            sys.exit(0)
        for i in range(len(account[0])):
            FN_TEXT(i + 1, f"{account[1][i]} : {account[0][i]}")
        while True:
            try:
                account_id = choose_input("NHẬP TÀI KHOẢN : ")
                if ',' in account_id:
                    account_id_list = account_id.split(',')
                    break
                else:
                    if int(account_id) > 0 and int(account_id) <= len(account[1]):
                        account_id_list = [account_id]
                        break
            except:
                pass
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("CONFIG")
        cookieslist = []
        if len(account_id_list) == 1:
            if check_cookies("INSTAGRAM", str(account[1][int(account_id_list[0]) - 1])) == False:
                while True:
                    try:
                        COOKIES = input_text("Nhập Cookies : ")
                        check = INSTAGRAM(COOKIES).GETINFO()
                        if check != False:
                            ADD_COOKIES("INSTAGRAM", str(account[1][int(account_id_list[0]) - 1]), COOKIES)
                            break
                    except KeyboardInterrupt:
                        sys.exit(0)
            else:
                for i in range(1, 4):
                    msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                    clear = " " * (80 - len(msg))
                    print(f"\r{msg}{clear}", end="")
                    sys.stdout.flush()
                    sleep(0.5)
                data = LoadJSON()
                COOKIES = data['data']['MXH']["INSTAGRAM"]['auth'][str(account[1][int(account_id_list[0]) - 1])]
                check = INSTAGRAM(COOKIES).GETINFO()
                if check != False:
                    print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
                else:
                    print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                    data['data']['MXH']["INSTAGRAM"]['auth'][str(account[1][int(account_id_list[0]) - 1])] = ""
                    SaveJSON(data)
                    print("\r" + " " * 50 + "\r", end="")
                    while True:
                        try:
                            COOKIES = input_text("Nhập Cookies : ")
                            check = INSTAGRAM(COOKIES).GETINFO()
                            if check != False:
                                ADD_COOKIES("INSTAGRAM", str(account[1][int(account_id_list[0]) - 1]), COOKIES)
                                break
                        except KeyboardInterrupt:
                            sys.exit(0)
            data = LoadJSON()
            cookieslist.append({str(account[1][int(account_id_list[0]) - 1]): data['data']['MXH']["INSTAGRAM"]['auth'][str(account[1][int(account_id_list[0]) - 1])]})
        else:
            for j in range(len(account_id_list)):
                if check_cookies("INSTAGRAM", str(account[1][int(account_id_list[j]) - 1])) == False:
                    while True:
                        try:
                            COOKIES = input_text(f"Nhập Cookies {Color.GREEN}{str(account[0][int(account_id_list[j]) - 1])}: ")
                            check = INSTAGRAM(COOKIES).GETINFO()
                            if check != False:
                                ADD_COOKIES("INSTAGRAM", str(account[1][int(account_id_list[j]) - 1]), COOKIES)
                                break
                        except KeyboardInterrupt:
                            sys.exit(0)
                else:
                    for i in range(1, 4):
                        msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                        clear = " " * (80 - len(msg))
                        print(f"\r{msg}{clear}", end="")
                        sys.stdout.flush()
                        sleep(0.5)
                    data = LoadJSON()
                    COOKIES = data['data']['MXH']["INSTAGRAM"]['auth'][str(account[1][int(account_id_list[j]) - 1])]
                    check = INSTAGRAM(COOKIES).GETINFO()
                    if check != False:
                        print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
                    else:
                        print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                        data['data']['MXH']["INSTAGRAM"]['auth'][str(account[1][int(account_id_list[j]) - 1])] = ""
                        SaveJSON(data)
                        print("\r" + " " * 50 + "\r", end="")
                        while True:
                            try:
                                COOKIES = input_text(f"Nhập Cookies {Color.GREEN}{str(account[0][int(account_id_list[j]) - 1])}: ")
                                check = INSTAGRAM(COOKIES).GETINFO()
                                if check != False:
                                    ADD_COOKIES("INSTAGRAM", str(account[1][int(account_id_list[j]) - 1]), COOKIES)
                                    break
                            except KeyboardInterrupt:
                                sys.exit(0)
                data = LoadJSON()
                cookieslist.append({str(account[1][int(account_id_list[j]) - 1]): data['data']['MXH']["INSTAGRAM"]['auth'][str(account[1][int(account_id_list[j]) - 1])]})

        while True:
            try:
                delay = input_text("Nhập Delay Nhiệm Vụ (Hoặc random khi nhập 2 số cách nhau bằng dấu ',') : ")
                if "," in delay:
                    delay = delay.split(",")
                    delay = [int(x) for x in delay]
                    if delay[0] < delay[1] and min(delay) != 0:
                        delay_min = delay[0]
                        delay_max = delay[1]
                        break
                else:
                    if int(delay) > 0:
                        delay_min, delay_max = int(delay), int(delay)
                        break
            except:
                pass
        while True:
            try:
                block_idx = input_text("Sau bao nhiêu nhiệm vụ bị giới hạn thì đổi acc : ")
                if int(block_idx) > 0:
                    break
            except:
                pass

        draw_full_width_box("ĐANG AUTO")
        # Gọi service Instagram (cần import services - nhưng do gộp file, tạm thời in thông báo)
        warning_text("Chức năng Instagram đang được phát triển trong phiên bản gộp")
        warning_text("Vui lòng sử dụng phiên bản cũ hoặc tích hợp services.py")

    elif CHOOSE == "2":
        # Threads
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("THÔNG TIN TÀI KHOẢN")
        account = GOLIKE(auth).GET_ACC("threads", "threads_username")
        if len(account[0]) == 0:
            warning_text("KHÔNG CÓ TÀI KHOẢN ! VUI LÒNG VÀO GOLIKE ĐỂ THÊM TÀI KHOẢN")
            sys.exit(0)
        for i in range(len(account[0])):
            FN_TEXT(i + 1, f"{account[1][i]} : {account[0][i]}")
        while True:
            try:
                account_id = choose_input("NHẬP TÀI KHOẢN : ")
                if ',' in account_id:
                    account_id_list = account_id.split(',')
                    break
                else:
                    if int(account_id) > 0 and int(account_id) <= len(account[1]):
                        account_id_list = [account_id]
                        break
            except:
                pass
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("CONFIG")
        cookieslist = []
        if len(account_id_list) == 1:
            if check_cookies("THREADS", str(account[1][int(account_id_list[0]) - 1])) == False:
                while True:
                    try:
                        COOKIES = input_text("Nhập Cookies : ")
                        check = Thread(COOKIES).GETDATA()
                        if check != False:
                            ADD_COOKIES("THREADS", str(account[1][int(account_id_list[0]) - 1]), COOKIES)
                            break
                    except KeyboardInterrupt:
                        sys.exit(0)
            else:
                for i in range(1, 4):
                    msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                    clear = " " * (80 - len(msg))
                    print(f"\r{msg}{clear}", end="")
                    sys.stdout.flush()
                    sleep(0.5)
                data = LoadJSON()
                COOKIES = data['data']['MXH']["THREADS"]['auth'][str(account[1][int(account_id_list[0]) - 1])]
                check = Thread(COOKIES).GETDATA()
                if check != False:
                    print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
                else:
                    print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                    data['data']['MXH']["THREADS"]['auth'][str(account[1][int(account_id_list[0]) - 1])] = ""
                    SaveJSON(data)
                    print("\r" + " " * 50 + "\r", end="")
                    while True:
                        try:
                            COOKIES = input_text("Nhập Cookies : ")
                            check = Thread(COOKIES).GETDATA()
                            if check != False:
                                ADD_COOKIES("THREADS", str(account[1][int(account_id_list[0]) - 1]), COOKIES)
                                break
                        except KeyboardInterrupt:
                            sys.exit(0)
            data = LoadJSON()
            cookieslist.append({str(account[1][int(account_id_list[0]) - 1]): data['data']['MXH']["THREADS"]['auth'][str(account[1][int(account_id_list[0]) - 1])]})
        else:
            for j in range(len(account_id_list)):
                if check_cookies("THREADS", str(account[1][int(account_id_list[j]) - 1])) == False:
                    while True:
                        try:
                            COOKIES = input_text(f"Nhập Cookies {Color.GREEN}{str(account[0][int(account_id_list[j]) - 1])}: ")
                            check = Thread(COOKIES).GETDATA()
                            if check != False:
                                ADD_COOKIES("THREADS", str(account[1][int(account_id_list[j]) - 1]), COOKIES)
                                break
                        except KeyboardInterrupt:
                            sys.exit(0)
                else:
                    for i in range(1, 4):
                        msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                        clear = " " * (80 - len(msg))
                        print(f"\r{msg}{clear}", end="")
                        sys.stdout.flush()
                        sleep(0.5)
                    data = LoadJSON()
                    COOKIES = data['data']['MXH']["THREADS"]['auth'][str(account[1][int(account_id_list[j]) - 1])]
                    check = Thread(COOKIES).GETDATA()
                    if check != False:
                        print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
                    else:
                        print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                        data['data']['MXH']["THREADS"]['auth'][str(account[1][int(account_id_list[j]) - 1])] = ""
                        SaveJSON(data)
                        print("\r" + " " * 50 + "\r", end="")
                        while True:
                            try:
                                COOKIES = input_text(f"Nhập Cookies {Color.GREEN}{str(account[0][int(account_id_list[j]) - 1])}: ")
                                check = Thread(COOKIES).GETDATA()
                                if check != False:
                                    ADD_COOKIES("THREADS", str(account[1][int(account_id_list[j]) - 1]), COOKIES)
                                    break
                            except KeyboardInterrupt:
                                sys.exit(0)
                data = LoadJSON()
                cookieslist.append({str(account[1][int(account_id_list[j]) - 1]): data['data']['MXH']["THREADS"]['auth'][str(account[1][int(account_id_list[j]) - 1])]})

        while True:
            try:
                delay = input_text("Nhập Delay Nhiệm Vụ (Hoặc random khi nhập 2 số cách nhau bằng dấu ',') : ")
                if "," in delay:
                    delay = delay.split(",")
                    delay = [int(x) for x in delay]
                    if delay[0] < delay[1] and min(delay) != 0:
                        delay_min = delay[0]
                        delay_max = delay[1]
                        break
                else:
                    if int(delay) > 0:
                        delay_min, delay_max = int(delay), int(delay)
                        break
            except:
                pass

        draw_full_width_box("ĐANG AUTO")
        warning_text("Chức năng Threads đang được phát triển trong phiên bản gộp")

    elif CHOOSE == "3":
        # LinkedIn
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("THÔNG TIN TÀI KHOẢN")
        account = GOLIKE(auth).GET_ACC("linkedin", "name")
        if len(account[0]) == 0:
            warning_text("KHÔNG CÓ TÀI KHOẢN ! VUI LÒNG VÀO GOLIKE ĐỂ THÊM TÀI KHOẢN")
            sys.exit(0)
        for i in range(len(account[0])):
            FN_TEXT(i + 1, f"{account[1][i]} : {account[0][i]}")
        while True:
            try:
                account_id = choose_input("NHẬP TÀI KHOẢN : ")
                if int(account_id) > 0 and int(account_id) <= len(account[1]):
                    break
            except:
                pass
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("CONFIG")
        if check_cookies("LINKEDIN", str(account[1][int(account_id) - 1])) == False:
            while True:
                try:
                    COOKIES = input_text("Nhập Cookies : ")
                    check = Linkedin(COOKIES).GETDATA()
                    if check != False:
                        ADD_COOKIES("LINKEDIN", str(account[1][int(account_id) - 1]), COOKIES)
                        break
                except KeyboardInterrupt:
                    sys.exit(0)
        else:
            for i in range(1, 4):
                msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                clear = " " * (80 - len(msg))
                print(f"\r{msg}{clear}", end="")
                sys.stdout.flush()
                sleep(0.5)
            data = LoadJSON()
            COOKIES = data['data']['MXH']["LINKEDIN"]['auth'][str(account[1][int(account_id) - 1])]
            check = Linkedin(COOKIES).GETDATA()
            if check != False:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
            else:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                data['data']['MXH']["LINKEDIN"]['auth'][str(account[1][int(account_id) - 1])] = ""
                SaveJSON(data)
                print("\r" + " " * 50 + "\r", end="")
                while True:
                    try:
                        COOKIES = input_text("Nhập Cookies : ")
                        check = Linkedin(COOKIES).GETDATA()
                        if check != False:
                            ADD_COOKIES("LINKEDIN", str(account[1][int(account_id) - 1]), COOKIES)
                            break
                    except KeyboardInterrupt:
                        sys.exit(0)

        while True:
            try:
                delay = input_text("Nhập Delay Nhiệm Vụ (Hoặc random khi nhập 2 số cách nhau bằng dấu ',') : ")
                if "," in delay:
                    delay = delay.split(",")
                    delay = [int(x) for x in delay]
                    if delay[0] < delay[1] and min(delay) != 0:
                        delay_min = delay[0]
                        delay_max = delay[1]
                        break
                else:
                    if int(delay) > 0:
                        delay_min, delay_max = int(delay), int(delay)
                        break
            except:
                pass

        draw_full_width_box("ĐANG AUTO")
        warning_text("Chức năng LinkedIn đang được phát triển trong phiên bản gộp")

    elif CHOOSE == "4":
        # Pinterest
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("THÔNG TIN TÀI KHOẢN")
        account = GOLIKE(auth).GET_ACC("pinterest", "name")
        if len(account[0]) == 0:
            warning_text("KHÔNG CÓ TÀI KHOẢN ! VUI LÒNG VÀO GOLIKE ĐỂ THÊM TÀI KHOẢN")
            sys.exit(0)
        for i in range(len(account[0])):
            FN_TEXT(i + 1, f"{account[1][i]} : {account[0][i]}")
        while True:
            try:
                account_id = choose_input("NHẬP TÀI KHOẢN : ")
                if int(account_id) > 0 and int(account_id) <= len(account[1]):
                    break
            except:
                pass
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("CONFIG")
        if check_cookies("PINTEREST", str(account[1][int(account_id) - 1])) == False:
            while True:
                try:
                    COOKIES = input_text("Nhập Cookies : ")
                    check = Pinterest(COOKIES).GETDATA()
                    if check != False:
                        ADD_COOKIES("PINTEREST", str(account[1][int(account_id) - 1]), COOKIES)
                        break
                except KeyboardInterrupt:
                    sys.exit(0)
        else:
            for i in range(1, 4):
                msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                clear = " " * (80 - len(msg))
                print(f"\r{msg}{clear}", end="")
                sys.stdout.flush()
                sleep(0.5)
            data = LoadJSON()
            COOKIES = data['data']['MXH']["PINTEREST"]['auth'][str(account[1][int(account_id) - 1])]
            check = Pinterest(COOKIES).GETDATA()
            if check != False:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
            else:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                data['data']['MXH']["PINTEREST"]['auth'][str(account[1][int(account_id) - 1])] = ""
                SaveJSON(data)
                print("\r" + " " * 50 + "\r", end="")
                while True:
                    try:
                        COOKIES = input_text("Nhập Cookies : ")
                        check = Pinterest(COOKIES).GETDATA()
                        if check != False:
                            ADD_COOKIES("PINTEREST", str(account[1][int(account_id) - 1]), COOKIES)
                            break
                    except KeyboardInterrupt:
                        sys.exit(0)

        while True:
            try:
                delay = input_text("Nhập Delay Nhiệm Vụ (Hoặc random khi nhập 2 số cách nhau bằng dấu ',') : ")
                if "," in delay:
                    delay = delay.split(",")
                    delay = [int(x) for x in delay]
                    if delay[0] < delay[1] and min(delay) != 0:
                        delay_min = delay[0]
                        delay_max = delay[1]
                        break
                else:
                    if int(delay) > 0:
                        delay_min, delay_max = int(delay), int(delay)
                        break
            except:
                pass

        draw_full_width_box("ĐANG AUTO")
        warning_text("Chức năng Pinterest đang được phát triển trong phiên bản gộp")

    elif CHOOSE == "16":
        # YouTube
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("THÔNG TIN TÀI KHOẢN")
        account = GOLIKE(auth).GET_ACC("youtube", "name")
        if len(account[0]) == 0:
            warning_text("KHÔNG CÓ TÀI KHOẢN ! VUI LÒNG VÀO GOLIKE ĐỂ THÊM TÀI KHOẢN")
            sys.exit(0)
        for i in range(len(account[0])):
            FN_TEXT(i + 1, f"{account[1][i]} : {account[0][i]}")
        while True:
            try:
                account_id = choose_input("NHẬP TÀI KHOẢN : ")
                if int(account_id) > 0 and int(account_id) <= len(account[1]):
                    break
            except:
                pass
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("CONFIG")
        if check_cookies("YOUTUBE", str(account[1][int(account_id) - 1])) == False:
            while True:
                try:
                    COOKIES = input_text("Nhập Cookies : ")
                    yt = YouTube(COOKIES)
                    check = yt.GETDATA()
                    if check != False:
                        ADD_COOKIES("YOUTUBE", str(account[1][int(account_id) - 1]), COOKIES)
                        break
                except KeyboardInterrupt:
                    sys.exit(0)
        else:
            for i in range(1, 4):
                msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                clear = " " * (80 - len(msg))
                print(f"\r{msg}{clear}", end="")
                sys.stdout.flush()
                sleep(0.5)
            data = LoadJSON()
            COOKIES = data['data']['MXH']["YOUTUBE"]['auth'][str(account[1][int(account_id) - 1])]
            yt = YouTube(COOKIES)
            check = yt.GETDATA()
            if check != False:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
            else:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                data['data']['MXH']["YOUTUBE"]['auth'][str(account[1][int(account_id) - 1])] = ""
                SaveJSON(data)
                print("\r" + " " * 50 + "\r", end="")
                while True:
                    try:
                        COOKIES = input_text("Nhập Cookies : ")
                        yt = YouTube(COOKIES)
                        check = yt.GETDATA()
                        if check != False:
                            ADD_COOKIES("YOUTUBE", str(account[1][int(account_id) - 1]), COOKIES)
                            break
                    except KeyboardInterrupt:
                        sys.exit(0)

        while True:
            try:
                delay = input_text("Nhập Delay Nhiệm Vụ (Hoặc random khi nhập 2 số cách nhau bằng dấu ',') : ")
                if "," in delay:
                    delay = delay.split(",")
                    delay = [int(x) for x in delay]
                    if delay[0] < delay[1] and min(delay) != 0:
                        delay_min = delay[0]
                        delay_max = delay[1]
                        break
                else:
                    if int(delay) > 0:
                        delay_min, delay_max = int(delay), int(delay)
                        break
            except:
                pass

        draw_full_width_box("ĐANG AUTO")
        warning_text("Chức năng YouTube đang được phát triển trong phiên bản gộp")

    elif CHOOSE == "17":
        # BlueSky
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("THÔNG TIN TÀI KHOẢN")
        account = GOLIKE(auth).GET_ACC("bluesky", "bluesky_username")
        if len(account[0]) == 0:
            warning_text("KHÔNG CÓ TÀI KHOẢN ! VUI LÒNG VÀO GOLIKE ĐỂ THÊM TÀI KHOẢN")
            sys.exit(0)
        for i in range(len(account[0])):
            FN_TEXT(i + 1, f"{account[1][i]} : {account[0][i]}")
        while True:
            try:
                account_id = choose_input("NHẬP TÀI KHOẢN : ")
                if int(account_id) > 0 and int(account_id) <= len(account[1]):
                    break
            except:
                pass
        os.system("cls" if os.name == "nt" else "clear")
        ascii_img()
        draw_full_width_box("CONFIG")
        if check_cookies("BLUESKY", str(account[1][int(account_id) - 1])) == False:
            while True:
                try:
                    COOKIES = input_text("Nhập Authorization BlueSky : ")
                    check = BlueSky(COOKIES).GETDATA()
                    if check != False:
                        ADD_COOKIES("BLUESKY", str(account[1][int(account_id) - 1]), COOKIES)
                        break
                except KeyboardInterrupt:
                    sys.exit(0)
        else:
            for i in range(1, 4):
                msg = f"{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}]{Color.END} => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}" + "." * i
                clear = " " * (80 - len(msg))
                print(f"\r{msg}{clear}", end="")
                sys.stdout.flush()
                sleep(0.5)
            data = LoadJSON()
            COOKIES = data['data']['MXH']["BLUESKY"]['auth'][str(account[1][int(account_id) - 1])]
            check = BlueSky(COOKIES).GETDATA()
            if check != False:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_GREEN}LIVE")
            else:
                print(f"\r{Color.LIGHT_CYAN}[{Color.END}^_^{Color.LIGHT_CYAN}{Color.END}] => {Color.LIGHT_PURPLE}Đang check cookie{Color.END}...{Color.LIGHT_RED}DIE")
                data['data']['MXH']["BLUESKY"]['auth'][str(account[1][int(account_id) - 1])] = ""
                SaveJSON(data)
                print("\r" + " " * 50 + "\r", end="")
                while True:
                    try:
                        COOKIES = input_text("Nhập Authorization BlueSky : ")
                        check = BlueSky(COOKIES).GETDATA()
                        if check != False:
                            ADD_COOKIES("BLUESKY", str(account[1][int(account_id) - 1]), COOKIES)
                            break
                    except KeyboardInterrupt:
                        sys.exit(0)

        while True:
            try:
                delay = input_text("Nhập Delay Nhiệm Vụ (Hoặc random khi nhập 2 số cách nhau bằng dấu ',') : ")
                if "," in delay:
                    delay = delay.split(",")
                    delay = [int(x) for x in delay]
                    if delay[0] < delay[1] and min(delay) != 0:
                        delay_min = delay[0]
                        delay_max = delay[1]
                        break
                else:
                    if int(delay) > 0:
                        delay_min, delay_max = int(delay), int(delay)
                        break
            except:
                pass

        draw_full_width_box("ĐANG AUTO")
        warning_text("Chức năng BlueSky đang được phát triển trong phiên bản gộp")

    else:
        warning_text(f"Chức năng {CHOOSE} chưa được hỗ trợ trong phiên bản gộp này")
        warning_text("Vui lòng tích hợp services.py hoặc sử dụng phiên bản cũ")


def main():
    os.system("cls" if os.name == "nt" else "clear")
    ascii_img()
    split_terminal()
    draw_full_width_box("THÔNG TIN TÀI KHOẢN")
    data = LoadJSON()
    if data['data']['Auth'] == "":
        warning_text("Bạn chưa nhập authorization vui lòng nhập authorization ! ")
        while True:
            auth = input_text("Nhập Authorization : ")
            check = GOLIKE(auth).GET_USER()
            if check != False:
                data['data']['Auth'] = auth
                SaveJSON(data)
                break
        main()
    else:
        info = GOLIKE(data['data']['Auth']).GET_USER()
        sleep(3)
        if info != False:
            menu_live(info, data['data']['Auth'])
        else:
            data['data']['Auth'] = ""
            SaveJSON(data)
            main()


if __name__ == "__main__":
    main()