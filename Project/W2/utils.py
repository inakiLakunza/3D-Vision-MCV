import numpy as np
import math
from math import ceil
import sys
import matplotlib.pyplot as plt
from scipy.ndimage import map_coordinates
import random
import plotly.graph_objects as go

def plot_img(img, do_not_use=[0]):
    plt.figure(do_not_use[0])
    do_not_use[0] += 1
    plt.imshow(img)


def get_transformed_pixels_coords(I, H, shift=None):
    ys, xs = np.indices(I.shape[:2]).astype("float64")
    if shift is not None:
        ys += shift[1]
        xs += shift[0]
    ones = np.ones(I.shape[:2])
    coords = np.stack((xs, ys, ones), axis=2)
    coords_H = (H @ coords.reshape(-1, 3).T).T
    coords_H /= coords_H[:, 2, np.newaxis]
    cart_H = coords_H[:, :2]
    
    return cart_H.reshape((*I.shape[:2], 2))

def apply_H_fixed_image_size(I, H, corners):
    h, w = I.shape[:2] # when we convert to np.array it swaps
    
    # corners
    c1 = np.array([1, 1, 1])
    c2 = np.array([w, 1, 1])
    c3 = np.array([1, h, 1])
    c4 = np.array([w, h, 1])
    
    # transformed corners
    Hc1 = H @ c1
    Hc2 = H @ c2
    Hc3 = H @ c3
    Hc4 = H @ c4
    Hc1 = Hc1 / Hc1[2]
    Hc2 = Hc2 / Hc2[2]
    Hc3 = Hc3 / Hc3[2]
    Hc4 = Hc4 / Hc4[2]
    
    xmin = corners[0]
    xmax = corners[1]
    ymin = corners[2]
    ymax = corners[3]

    size_x = ceil(xmax - xmin + 1)
    size_y = ceil(ymax - ymin + 1)
    
    # transform image
    H_inv = np.linalg.inv(H)
    
    out = np.zeros((size_y, size_x, 3))
    shift = (xmin, ymin)
    interpolation_coords = get_transformed_pixels_coords(out, H_inv, shift=shift)
    interpolation_coords[:, :, [0, 1]] = interpolation_coords[:, :, [1, 0]]
    interpolation_coords = np.swapaxes(np.swapaxes(interpolation_coords, 0, 2), 1, 2)
    
    out[:, :, 0] = map_coordinates(I[:, :, 0], interpolation_coords)
    out[:, :, 1] = map_coordinates(I[:, :, 1], interpolation_coords)
    out[:, :, 2] = map_coordinates(I[:, :, 2], interpolation_coords)
    
    return out.astype("uint8")

def Normalise_last_coord(x):
    xn = x  / x[2,:]
    
    return xn

def DLT_homography(points1, points2):
    
    # ToDo: complete this code .......
    # 1. For each point set apply a normalization
    
         #Image1
    
    mean, std = np.mean(points1, 0), np.std(points1)
    
    # define similarity transformation
    # no rotation, scaling using sdv and setting centroid as origin
    Transformation = np.array([[std/np.sqrt(2), 0, mean[0]],
                               [0, std/np.sqrt(2), mean[1]],
                               [0,   0, 1]])
    
    # apply transformation on data points
    Transformation = np.linalg.inv(Transformation)
    points1 = np.dot(Transformation, points1)
    p1T = points1.T
    
    
        #Image2
    mean, std = np.mean(points2, 0), np.std(points2)
    
    # define similarity transformation
    # no rotation, scaling using sdv and setting centroid as origin
    Transformation2 = np.array([[std/np.sqrt(2), 0, mean[0]],
                               [0, std/np.sqrt(2), mean[1]],
                               [0,   0, 1]])
    
    # apply transformation on data points
    Transformation2 = np.linalg.inv(Transformation2)
    points2 = np.dot(Transformation2, points2)
    p2T = points2.T
    
    # 2. For each correscpondence x_i <-> x'_i , compute A_i
    
    A=[]
    for i in range(len(points1.T)):
        x1, y1, w1 = p1T[i]
        x2, y2, w2 = p2T[i]
        
        Ai = [[    0,     0,     0,  -w2*x1, -w2*y1, -w2*w1,   y2*x1,  y2*y1,  y2*w1],
              [w2*x1, w2*y1, w2*w1,       0,      0,      0,  -x2*x1, -x2*y1, -x2*w1]]
        
        
        A.append(Ai)
    
    # 3. Assemble the n matrices A_i to form the 2nx9 matrix A (in this case n=4)
    A = np.concatenate(A, axis=0)
    
        # Shape of A should be 2x4*9 = 8*9
    #print("A:", len(A), len(A[0]))
    
    
    # 4.1 Compute the SVD decomposition of A
    U, D, Vt = np.linalg.svd(A)
    
    # 4.2 h is the last column of V, and H is h reshaped by 3x3
    h = Vt[-1]
    H = h.reshape((3, 3))
    
    # 5. denormalize to obtain homography (H) using the transformations and generalized pseudo-inverse
    H = np.dot(np.dot(np.linalg.pinv(Transformation2), H), Transformation)
  
    return H

def Inliers(H, points1, points2, th):
    
    # Check that H is invertible
    if abs(math.log(np.linalg.cond(H))) > 15:
        idx = np.empty(1)
        return idx
    # ToDo: complete this code .......
    num_points = points1.shape[1]
    inliers = []

    for i in range(num_points):
        # Transform points from the first image to the second image using the homography
        transformed_point = H @ points1[:, i]
        transformed_point /= transformed_point[2]  # Normalize by the homogeneous coordinate
        
        # Calculate Euclidean distance between transformed point and corresponding point in image 2
        dist = np.linalg.norm(transformed_point - points2[:, i])
        
        # Check if the distance is within the threshold
        if dist < th:
            inliers.append(i)
    
    inliers = np.array(inliers)
    return inliers
    

def Ransac_DLT_homography(points1, points2, th, max_it):
    
    Ncoords, Npts = points1.shape
    
    it = 0
    best_inliers = np.empty(1)
    
    while it < max_it:
        indices = random.sample(range(1, Npts), 4)
        H = DLT_homography(points1[:,indices], points2[:,indices])
        inliers = Inliers(H, points1, points2, th)
        
        # test if it is the best model so far
        if inliers.shape[0] > best_inliers.shape[0]:
            best_inliers = inliers
        
        # update estimate of iterations (the number of trials) to ensure we pick, with probability p,
        # an initial data set with no outliers
        fracinliers = inliers.shape[0]/Npts
        pNoOutliers = 1 -  fracinliers**4
        eps = sys.float_info.epsilon
        pNoOutliers = max(eps, pNoOutliers)   # avoid division by -Inf
        pNoOutliers = min(1-eps, pNoOutliers) # avoid division by 0
        p = 0.99
        max_it = math.log(1-p)/math.log(pNoOutliers)
        
        it += 1
    
    # compute H from all the inliers
    H = DLT_homography(points1[:,best_inliers], points2[:,best_inliers])
    inliers = best_inliers
    
    return H, inliers



def optical_center(P):
    U, d, Vt = np.linalg.svd(P)
    o = Vt[-1, :3] / Vt[-1, -1]
    return o

def view_direction(P, x):
    # Vector pointing to the viewing direction of a pixel
    # We solve x = P v with v(3) = 0
    v = np.linalg.inv(P[:,:3]) @ np.array([x[0], x[1], 1])
    return v

def plot_camera(P, w, h, fig, legend):
    
    o = optical_center(P)
    scale = 200
    p1 = o + view_direction(P, [0, 0]) * scale
    p2 = o + view_direction(P, [w, 0]) * scale
    p3 = o + view_direction(P, [w, h]) * scale
    p4 = o + view_direction(P, [0, h]) * scale
    
    x = np.array([p1[0], p2[0], o[0], p3[0], p2[0], p3[0], p4[0], p1[0], o[0], p4[0], o[0], (p1[0]+p2[0])/2])
    y = np.array([p1[1], p2[1], o[1], p3[1], p2[1], p3[1], p4[1], p1[1], o[1], p4[1], o[1], (p1[1]+p2[1])/2])
    z = np.array([p1[2], p2[2], o[2], p3[2], p2[2], p3[2], p4[2], p1[2], o[2], p4[2], o[2], (p1[2]+p2[2])/2])
    
    fig.add_trace(go.Scatter3d(x=x, y=z, z=-y, mode='lines',name=legend))
    
    return

def plot_image_origin(w, h, fig, legend):
    p1 = np.array([0, 0, 0])
    p2 = np.array([w, 0, 0])
    p3 = np.array([w, h, 0])
    p4 = np.array([0, h, 0])
    
    x = np.array([p1[0], p2[0], p3[0], p4[0], p1[0]])
    y = np.array([p1[1], p2[1], p3[1], p4[1], p1[1]])
    z = np.array([p1[2], p2[2], p3[2], p4[2], p1[2]])
    
    fig.add_trace(go.Scatter3d(x=x, y=z, z=-y, mode='lines',name=legend))
    
    return
