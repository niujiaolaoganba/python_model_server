# -*-coding:utf-8-*-

import six,os,sys,base64,time,datetime,unicodedata,hmac,hashlib, random as _random
from six.moves import builtins
from tornado import escape
if six.PY2 and sys.getdefaultencoding() != 'utf8':
    reload(sys)
    sys.setdefaultencoding('utf8')

THIS_DIRNAME = os.path.abspath(os.getcwd())
FINUP_OTP_SALT = 'abaelhe@icloud.com'
FINUP_OTP_CODE = base64.b32encode(six.b('heyijun@finupgroup.com' + FINUP_OTP_SALT))
FINUP_OTP_KEY_FILE  =os.sep.join([THIS_DIRNAME, 'logs', 'finup_otp.key' ])
FINUP_OTP_KEY  = None
FINUP_OTP = None

def OTP_input(otp_key_file):
    try:
        with open(otp_key_file, 'rb') as otpf:
            file_otp_key = otpf.read().strip()
            if len(file_otp_key) == 6 and file_otp_key.isdigit():
                return file_otp_key
    except:
        print('请输入OTP单次授权启动密钥:')

    try:
        input_otp_key = str(six.moves.input()).strip()
        if len(input_otp_key) != 6 or not input_otp_key.isdigit():
            print(u"OTP密钥(6位数字)格式不正确!")
            sys.exit(-999)
        with open(otp_key_file, 'wb') as otpf:
            otpf.write(escape.utf8(input_otp_key))
            otpf.flush()
        return input_otp_key
    except:
        print(
u'''
    确保 OTP授权启动文件存在( "%s" )，
    而且仅包含单次启动OTP密钥(6位数字).
''' % (otp_key_file))
        print(u"OTP密钥(6位数字)保存失败.")
        sys.exit(-998)

####
def OTP_init(otp_key_path = FINUP_OTP_KEY_FILE, retry=0):

    if retry == 5:
        print('OTP密钥验证失败, 请联系 凡普金科 获取.')
        sys.exit(-998)
    otp_key = OTP_input(otp_key_path)
    if escape.utf8(FINUP_OTP.now()) == escape.utf8(otp_key):
        return True
    else:
        time.sleep(retry * 5)

    try:
        os.remove(otp_key_path)
    except:
        pass
    OTP_init(otp_key_path, retry+1)



USING_PYTHON2 = True if sys.version_info < (3, 0) else False
str = unicode if USING_PYTHON2 else str # noqa

try:
    from itertools import izip_longest
except ImportError:
    from itertools import zip_longest as izip_longest

try:
    from urllib.parse import quote, urlencode
except ImportError:
    from urllib import quote, urlencode

def random_base32(length=16, random=_random.SystemRandom(), chars=list('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')):
    return ''.join( random.choice(chars) for _ in range(length) )

def build_uri(secret, name, initial_count=None, issuer_name=None, algorithm=None, digits=None, period=None):
    is_initial_count_present = (initial_count is not None)

    is_algorithm_set = (algorithm is not None and algorithm != 'sha1')
    is_digits_set = (digits is not None and digits != 6)
    is_period_set = (period is not None and period != 30)

    otp_type = 'hotp' if is_initial_count_present else 'totp'
    base_uri = 'otpauth://{0}/{1}?{2}'

    url_args = {'secret': secret}

    label = quote(name)
    if issuer_name is not None:
        label = quote(issuer_name) + ':' + label
        url_args['issuer'] = issuer_name

    if is_initial_count_present:
        url_args['counter'] = initial_count
    if is_algorithm_set:
        url_args['algorithm'] = algorithm.upper()
    if is_digits_set:
        url_args['digits'] = digits
    if is_period_set:
        url_args['period'] = period

    uri = base_uri.format(otp_type, label, urlencode(url_args).replace("+", "%20"))
    return uri


def _compare_digest(s1, s2):
    differences = 0
    for c1, c2 in izip_longest(s1, s2):
        if c1 is None or c2 is None:
            differences = 1
            continue
        differences |= ord(c1) ^ ord(c2)
    return differences == 0

try:
    from hmac import compare_digest
except ImportError:
    compare_digest = _compare_digest


def strings_equal(s1, s2):
    s1 = unicodedata.normalize('NFKC', s1)
    s2 = unicodedata.normalize('NFKC', s2)
    return compare_digest(s1, s2)

#### OTP
class OTP(object):
    def __init__(self, s, digits=6, digest=hashlib.sha1):
        self.digits = digits
        self.digest = digest
        self.secret = s

    def generate_otp(self, input):
        if input < 0:
            raise ValueError('input must be positive integer')
        hasher = hmac.new(self.byte_secret(), self.int_to_bytestring(input), self.digest)
        hmac_hash = bytearray(hasher.digest())
        offset = hmac_hash[-1] & 0xf
        code = ((hmac_hash[offset] & 0x7f) << 24 |
                (hmac_hash[offset + 1] & 0xff) << 16 |
                (hmac_hash[offset + 2] & 0xff) << 8 |
                (hmac_hash[offset + 3] & 0xff))
        str_code = str(code % 10 ** self.digits)
        while len(str_code) < self.digits:
            str_code = '0' + str_code

        return str_code

    def byte_secret(self):
        missing_padding = len(self.secret) % 8
        if missing_padding != 0:
            self.secret += '=' * (8 - missing_padding)
        return base64.b32decode(self.secret, casefold=True)

    @staticmethod
    def int_to_bytestring(i, padding=8):
        result = bytearray()
        while i != 0:
            result.append(i & 0xFF)
            i >>= 8
        return bytes(bytearray(reversed(result)).rjust(padding, b'\0'))

#### HOTP
class HOTP(OTP):
    def at(self, count):
        return self.generate_otp(count)

    def verify(self, otp, counter):
        return strings_equal(str(otp), str(self.at(counter)))

    def provisioning_uri(self, name, initial_count=0, issuer_name=None):
        return build_uri( self.secret, name, initial_count=initial_count, issuer_name=issuer_name, algorithm=self.digest().name, digits=self.digits)

#### TOTP
class TOTP(OTP):
    def __init__(self, *args, **kwargs):
        self.interval = kwargs.pop('interval', 30)
        super(TOTP, self).__init__(*args, **kwargs)

    def at(self, for_time, counter_offset=0):
        if not isinstance(for_time, datetime.datetime):
            for_time = datetime.datetime.fromtimestamp(int(for_time))
        return self.generate_otp(self.timecode(for_time) + counter_offset)

    def now(self):
        return self.generate_otp(self.timecode(datetime.datetime.now()))

    def verify(self, otp, for_time=None, valid_window=0):
        if for_time is None:
            for_time = datetime.datetime.now()

        if valid_window:
            for i in range(-valid_window, valid_window + 1):
                if strings_equal(str(otp), str(self.at(for_time, i))):
                    return True
            return False

        return strings_equal(str(otp), str(self.at(for_time)))

    def provisioning_uri(self, name, issuer_name=None):
        return build_uri(self.secret, name, issuer_name=issuer_name, algorithm=self.digest().name, digits=self.digits, period=self.interval)

    def timecode(self, for_time):
        i = time.mktime(for_time.timetuple())
        return int(i / self.interval)


if FINUP_OTP is None:
    FINUP_OTP = TOTP(FINUP_OTP_CODE)

