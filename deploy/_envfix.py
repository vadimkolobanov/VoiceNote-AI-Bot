p = '/opt/methodex/.env'
text = open(p).read()
text = text.replace(
    'YANDEX_SPEECHKIT_FOLDER_ID=b1g6kkv42rrqh4a51261ADMIN_TELEGRAM_ID=5736197809',
    'YANDEX_SPEECHKIT_FOLDER_ID=b1g6kkv42rrqh4a51261\nADMIN_TELEGRAM_ID=5736197809',
)
if not text.endswith('\n'):
    text += '\n'
open(p, 'w').write(text)
print('fixed')
