import cv2
import random
import numpy as np
from autocorrect import Speller
from model import Model, DecoderType
from path import Path
from tensorflow.python.framework import ops
import logging

logging.getLogger("tensorflow").disabled = True


def preprocess(img, imgSize, dataAugmentation=False):
    "put img into target img of size imgSize, transpose for TF and normalize gray-values"

    # there are damaged files in IAM dataset - just use black image instead
    if img is None:
        img = np.zeros(imgSize[::-1])

    # data augmentation
    img = img.astype(np.float)
    if dataAugmentation:
        # photometric data augmentation
        if random.random() < 0.25:
            rand_odd = lambda: random.randint(1, 3) * 2 + 1
            img = cv2.GaussianBlur(img, (rand_odd(), rand_odd()), 0)
        if random.random() < 0.25:
            img = cv2.dilate(img, np.ones((3, 3)))
        if random.random() < 0.25:
            img = cv2.erode(img, np.ones((3, 3)))
        if random.random() < 0.5:
            img = img * (0.25 + random.random() * 0.75)
        if random.random() < 0.25:
            img = np.clip(
                img + (np.random.random(img.shape) - 0.5) * random.randint(1, 50),
                0,
                255,
            )
        if random.random() < 0.1:
            img = 255 - img

        # geometric data augmentation
        wt, ht = imgSize
        h, w = img.shape
        f = min(wt / w, ht / h)
        fx = f * np.random.uniform(0.75, 1.25)
        fy = f * np.random.uniform(0.75, 1.25)

        # random position around center
        txc = (wt - w * fx) / 2
        tyc = (ht - h * fy) / 2
        freedom_x = max((wt - fx * w) / 2, 0) + wt / 10
        freedom_y = max((ht - fy * h) / 2, 0) + ht / 10
        tx = txc + np.random.uniform(-freedom_x, freedom_x)
        ty = tyc + np.random.uniform(-freedom_y, freedom_y)

        # map image into target image
        M = np.float32([[fx, 0, tx], [0, fy, ty]])
        target = np.ones(imgSize[::-1]) * 255 / 2
        img = cv2.warpAffine(
            img, M, dsize=imgSize, dst=target, borderMode=cv2.BORDER_TRANSPARENT
        )

    # no data augmentation
    else:
        # center image
        wt, ht = imgSize
        h, w = img.shape
        f = min(wt / w, ht / h)
        tx = (wt - w * f) / 2
        ty = (ht - h * f) / 2

        # map image into target image
        M = np.float32([[f, 0, tx], [0, f, ty]])
        target = np.ones(imgSize[::-1]) * 255 / 2
        img = cv2.warpAffine(
            img, M, dsize=imgSize, dst=target, borderMode=cv2.BORDER_TRANSPARENT
        )

    # transpose for TF
    img = cv2.transpose(img)

    # convert to range [-1, 1]
    img = img / 255 - 0.5
    return img


class FilePaths:
    "filenames and paths to data"
    fnCharList = "../models/charList.txt"
    fnSummary = "../models/summary.json"


class Batch:
    "batch containing images and ground truth texts"

    def __init__(self, gtTexts, imgs):
        self.imgs = np.stack(imgs, axis=0)
        self.gtTexts = gtTexts


def predict(imgs):
    ops.reset_default_graph()
    decoderType = DecoderType.BeamSearch
    model = Model(open(FilePaths.fnCharList).read(), decoderType, mustRestore=True)
    spell = Speller(lang="en")
    result = []
    for img in imgs:
        img = preprocess(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), Model.imgSize)
        batch = Batch(None, [img])
        (recognized, probability) = model.inferBatch(batch, True)
        result.append(spell(recognized[0]))

    return " ".join(result)
