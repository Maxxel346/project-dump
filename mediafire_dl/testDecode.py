# decode base 64
import base64

def decode_base64(encoded_str):
    decoded_bytes = base64.b64decode(encoded_str)
    decoded_str = decoded_bytes.decode('utf-8')
    return decoded_str

encoded_str = "----some-random-string-here----"
decoded_url = decode_base64(encoded_str)
print("Decoded URL:", decoded_url)