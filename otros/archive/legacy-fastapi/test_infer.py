import requests, json, glob, os

imgs = glob.glob(r'C:\Users\JHON\Desktop\PROYECTO DE YOLO\hand-wash-compliance-yolo\HandWashDataset_yoloFormat\TrainingData\images\val\*.jpg')[:8]

for img in imgs:
    with open(img, 'rb') as f:
        r = requests.post('http://localhost:8001/api/infer', files={'file': f})
    d = r.json()
    name = os.path.basename(img)
    if d['manoDetectada']:
        hand = 'OK {:.2f}'.format(d['manoConfianza'])
    else:
        hand = 'NO'
    step = d.get('pasoDetectado') or '-'
    conf = d.get('pasoConfianza') or 0
    print('{:15s} Mano: {:12s} Paso: {:25s} ({:.2f})'.format(name, hand, step, conf))
