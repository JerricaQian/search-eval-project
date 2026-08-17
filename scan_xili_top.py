import numpy as np
from PIL import Image

img = np.array(Image.open('screenshots/喜力啤酒整箱_全部_1.png').convert('RGB'))
h, w = img.shape[:2]

bands = [(38,78), (120,210), (296,354), (423,468), (528,644), (676,710)]

for ys, ye in bands:
    band = img[ys:ye+1]
    col_has = []
    for x in range(w):
        col = band[:, x]
        nw = np.sum(~((col[:,0]>240)&(col[:,1]>240)&(col[:,2]>240)))
        if nw > (ye-ys+1) * 0.01:
            col_has.append(x)
    xr = f'{col_has[0]}-{col_has[-1]}' if col_has else 'none'
    green = np.sum((band[:,:,1]>120) & (band[:,:,0]<150) & (band[:,:,2]<150))
    red = np.sum((band[:,:,0]>180) & (band[:,:,1]<100) & (band[:,:,2]<100))
    yellow = np.sum((band[:,:,0]>200) & (band[:,:,1]>140) & (band[:,:,2]<100))
    dark = np.sum((band[:,:,0]<100) & (band[:,:,1]<100) & (band[:,:,2]<100))
    print(f'y={ys}-{ye} x={xr} green={green} red={red} yellow={yellow} dark={dark}')

seps = [(1057,1087), (1122,1153), (1186,1273), (1619,1650), (1685,1717), (1749,1836), (2187,2218), (2251,2335)]
for ys, ye in seps:
    band = img[ys:ye+1]
    nw = np.sum(~((band[:,:,0]>240)&(band[:,:,1]>240)&(band[:,:,2]>240)))
    print(f'Separator y={ys}-{ye}: nonwhite={nw}')
