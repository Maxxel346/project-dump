from uploader import upload_pixeldrain, upload_gofile, upload_mixdrop

# PixelDrain (requires API key):
res_pixeldrain = upload_pixeldrain("path/to/file.zip", "YOUR_PIXELDRAIN_API_KEY")
print(res_pixeldrain)
# Example output:
# {
#     "provider": "pixeldrain",
#     "id": "abc123",
#     "name": "file.zip"
# }

# GoFile (anonymous, no key required):
res_gofile = upload_gofile("path/to/file.zip")
print(res_gofile)
# Example output:
# {
#     "provider": "gofile",
#     "downloadPage": "https://gofile.io/d/abc123",
#     "folderId": "folder123",
#     "token": "guesttoken"
# }

# MixDrop (requires api email & key):
res_mixdrop = upload_mixdrop("path/to/file.zip", "user@domain.com", "MIXDROP_API_KEY", folder=None)
print(res_mixdrop)
# Example output:
# {
#     "provider": "mixdrop",
#     "fileref": "lOd3o",
#     "url": "https://domain.co/f/lOd3o",
#     "embedurl": "https://domain.co/e/lOd3o"
# }
