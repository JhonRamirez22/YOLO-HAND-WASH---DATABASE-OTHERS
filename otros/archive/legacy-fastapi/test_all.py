import requests, json, glob, os
from collections import Counter

imgs = glob.glob(r'C:\Users\JHON\Desktop\PROYECTO DE YOLO\hand-wash-compliance-yolo\HandWashDataset_yoloFormat\TrainingData\images\val\*.jpg')
print('Testing {} images...'.format(len(imgs)))

detected = 0
not_detected = 0
steps_found = Counter()

for img in imgs:
    with open(img, 'rb') as f:
        r = requests.post('http://localhost:8001/api/infer', files={'file': f})
    d = r.json()
    name = os.path.basename(img)
    if d['manoDetectada']:
        detected += 1
        step = d.get('pasoDetectado') or '-'
        conf = d.get('manoConfianza') or 0
        steps_found[step] += 1
        if conf > 0.3:
            print('  {:15s} Mano: {:.2f}  Paso: {}'.format(name, conf, step))
    else:
        not_detected += 1

print('\n--- RESULTS ---')
print('Detected:   {}'.format(detected))
print('Not found:  {}'.format(not_detected))
print('Ratio:      {:.0f}%'.format(100 * detected / len(imgs)))
print('Steps:')
for step, count in steps_found.most_common():
    print('  {:25s} {}'.format(step, count))
