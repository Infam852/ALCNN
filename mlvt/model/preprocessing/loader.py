import logging
import os
from pathlib import Path

import cv2
from tqdm import tqdm
from PIL import Image
from torchvision import transforms


LOG = logging.getLogger('MLVT')


class DataLoader:
    def __init__(self, cm, resize_without_ratio=False, img_size=224):
        self.cm = cm
        self.IMG_SIZE = cm.get_img_size()
        if resize_without_ratio:
            self.transforms = None
        else:
            self.transforms = transforms.Compose([
                transforms.Resize(self.IMG_SIZE),
                transforms.CenterCrop(img_size),
            ])

    def copy_multiple_paths(self, srcs, dsts):
        excs = []
        for src, dst in zip(srcs, dsts):
            try:
                self.copy_all(src, dst)
            except FileNotFoundError:
                excs.append(f'{srcs}, {dsts}')
        return excs

    def copy_all(self, src, dst):
        Path(dst).mkdir(parents=True, exist_ok=True)
        LOG.info(f'Start copying images from {src} to {dst}...')
        for f in tqdm(os.listdir(src)):
            src_path = os.path.join(src, f)
            if os.path.isfile(src_path):
                img = Image.open(src_path).convert('RGB')
                img = self.transforms(img) if self.transforms \
                    else img.resize((self.IMG_SIZE, self.IMG_SIZE))
                dst_path = os.path.join(dst, f)
                img.save(dst_path, quality=95)
        LOG.info(f'Images copied form {src} to {dst}.')

    def _rescale(self, img):
        """Rescale image to the specified in config file size.
        If rescale_with_crop flag is specified then the image is firstly
        resized that the shorter side has desired size then it is cropped.

        Args:
            img (array): array representation of an image

        Returns:
            array: array representation of rescaled image
        """
        if self.cm.do_rescale_with_crop():
            (h, w) = img.shape[:2]
            if h > w:
                ratio = h / w
                # dims: (w, h)
                dims = (self.IMG_SIZE, int(self.IMG_SIZE*ratio))
                img = cv2.resize(img, dims)
                crop_idx = (dims[1] - self.IMG_SIZE) // 2
                img = img[crop_idx:self.IMG_SIZE+crop_idx, :]
            else:
                ratio = w / h
                dims = (int(self.IMG_SIZE*ratio), self.IMG_SIZE)
                img = cv2.resize(img, dims)
                crop_idx = (dims[0] - self.IMG_SIZE) // 2
                img = img[:, crop_idx:self.IMG_SIZE+crop_idx]
        else:
            img = cv2.resize(img, (self.IMG_SIZE, self.IMG_SIZE))
        return img
