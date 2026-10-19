from PIL import Image
import numpy as np
import random

starting_tresholds = [0.5, 0.6, 0.5]
threshold_decrease_rates = [0.03, 0.05, 0.07]
cells=[[], [], []]

bush1 = Image.open("assets/environment/bush/bush1.png")
bush2 = Image.open("assets/environment/bush/bush2.png")
bush3 = Image.open("assets/environment/bush/bush3.png")

# Create a 5x5 array filled with zeros
array_of_bushes = np.zeros((7, 7))

array_of_bushes[3, 3] = 1

r=[-1, 0, 1]
c=[-1, 0, 1]


random.shuffle(r)
random.shuffle(c)
for i in r:
    for j in c:
        if i == 0 and j == 0:
            continue
        if random.random() < starting_tresholds[0]:    
            array_of_bushes[3 + i, 3 + j] = 1
            cells[0].append((3 + i, 3 + j))
            starting_tresholds[0] -= threshold_decrease_rates[0]

print(array_of_bushes)

for cell in cells[0]:
    print("--------------------------------")
    a=array_of_bushes[cell[0]-1:cell[0]+2, cell[1]-1:cell[1]+2]
    if np.sum(a)-array_of_bushes[cell[0], cell[1]] == 1:
        array_of_bushes[cell[0], cell[1]] = 0
        cells[0].remove(cell)
        print("True")



# random.shuffle(r)
# random.shuffle(c)
# for cell in cells[0]:
#     for i in r:
#         for j in c:
#             if array_of_bushes[cell[0] + i, cell[1] + j] == 1:
#                 continue
#             if random.random() < starting_tresholds[1]:
#                 array_of_bushes[cell[0] + i, cell[1] + j] = 2
#                 cells[1].append((cell[0] + i, cell[1] + j))
#                 starting_tresholds[1] -= threshold_decrease_rates[1]

# random.shuffle(r)
# random.shuffle(c)
# for cell in cells[1]:
#     for i in r:
#         for j in c:
#             if array_of_bushes[cell[0] + i, cell[1] + j] == 2:
#                 continue
#             if random.random() < starting_tresholds[2]:
#                 array_of_bushes[cell[0] + i, cell[1] + j] = 3
#                 cells[2].append((cell[0] + i, cell[1] + j))
#                 starting_tresholds[2] -= threshold_decrease_rates[2]

# for i in range(7):
#     for j in range(7):
#         a=array_of_bushes[i-1:i+2, j-1:j+2]
#         if np.sum(a)-array_of_bushes[i, j] <4:
#             array_of_bushes[i, j] = 0


print(array_of_bushes)
