import requests, glob, os

imgs = glob.glob(r'C:\Users\JHON\Desktop\PROYECTO DE YOLO\hand-wash-compliance-yolo\HandWashDataset_yoloFormat\TrainingData\images\val\*.jpg')[:20]
print('Testing {} images...'.format(len(imgs)))

detected = 0
for img in imgs:
    with open(img, 'rb') as f:
        r = requests.post('http://localhost:8001/api/infer', files={'file': f})
    d = r.json()
    name = os.path.basename(img)
    if d['manoDetectada']:
        detected += 1
        step = d.get('pasoDetectado') or '-'
        conf = d.get('manoConfianza') or 0
        print('  {:15s} Mano: {:.2f}  Paso: {}'.format(name, conf, step))
    else:
        print('  {:15s} -- no hand --'.format(name))

print('\nDetected: {}/{}'.format(detected, len(imgs)))
