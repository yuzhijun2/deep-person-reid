from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from PIL import Image
import random
import numpy as np
import math

import torch
from torchvision.transforms import *


class Random2DTranslation(object):
    """Randomly translates the input image with a probability.

    Specifically, given a predefined shape (height, width), the input is first
    resized with a factor of 1.125, leading to (height*1.125, width*1.125), then
    a random crop is performed. Such operation is done with a probability.

    Args:
        height (int): target image height.
        width (int): target image width.
        p (float, optional): probability that this operation takes place.
            Default is 0.5.
        interpolation (int, optional): desired interpolation. Default is
            ``PIL.Image.BILINEAR``
    """
    
    def __init__(self, height, width, p=0.5, interpolation=Image.BILINEAR):
        self.height = height
        self.width = width
        self.p = p
        self.interpolation = interpolation

    def __call__(self, img):
        if random.uniform(0, 1) > self.p:
            return img.resize((self.width, self.height), self.interpolation)
        
        new_width, new_height = int(round(self.width * 1.125)), int(round(self.height * 1.125))
        resized_img = img.resize((new_width, new_height), self.interpolation)
        x_maxrange = new_width - self.width
        y_maxrange = new_height - self.height
        x1 = int(round(random.uniform(0, x_maxrange)))
        y1 = int(round(random.uniform(0, y_maxrange)))
        croped_img = resized_img.crop((x1, y1, x1 + self.width, y1 + self.height))
        return croped_img


class RandomErasing(object):
    """Randomly erases an image patch.

    Origin: `<https://github.com/zhunzhong07/Random-Erasing>`_

    Reference:
        Zhong et al. Random Erasing Data Augmentation.

    Args:
        probability (float, optional): probability that this operation takes place.
            Default is 0.5.
        sl (float, optional): min erasing area.
        sh (float, optional): max erasing area.
        r1 (float, optional): min aspect ratio.
        mean (list, optional): erasing value.
    """
    
    def __init__(self, probability=0.5, sl=0.02, sh=0.4, r1=0.3, mean=[0.4914, 0.4822, 0.4465]):
        self.probability = probability
        self.mean = mean
        self.sl = sl
        self.sh = sh
        self.r1 = r1
       
    def __call__(self, img):
        if random.uniform(0, 1) > self.probability:
            return img

        for attempt in range(100):
            area = img.size()[1] * img.size()[2]
       
            target_area = random.uniform(self.sl, self.sh) * area
            aspect_ratio = random.uniform(self.r1, 1/self.r1)

            h = int(round(math.sqrt(target_area * aspect_ratio)))
            w = int(round(math.sqrt(target_area / aspect_ratio)))

            if w < img.size()[2] and h < img.size()[1]:
                x1 = random.randint(0, img.size()[1] - h)
                y1 = random.randint(0, img.size()[2] - w)
                if img.size()[0] == 3:
                    img[0, x1:x1+h, y1:y1+w] = self.mean[0]
                    img[1, x1:x1+h, y1:y1+w] = self.mean[1]
                    img[2, x1:x1+h, y1:y1+w] = self.mean[2]
                else:
                    img[0, x1:x1+h, y1:y1+w] = self.mean[0]
                return img

        return img


class ColorAugmentation(object):
    """Randomly alters the intensities of RGB channels.

    Reference:
        Krizhevsky et al. ImageNet Classification with Deep ConvolutionalNeural
        Networks. NIPS 2012.

    Args:
        p (float, optional): probability that this operation takes place.
            Default is 0.5.
    """
    
    def __init__(self, p=0.5):
        self.p = p
        self.eig_vec = torch.Tensor([
            [0.4009, 0.7192, -0.5675],
            [-0.8140, -0.0045, -0.5808],
            [0.4203, -0.6948, -0.5836],
        ])
        self.eig_val = torch.Tensor([[0.2175, 0.0188, 0.0045]])

    def _check_input(self, tensor):
        assert tensor.dim() == 3 and tensor.size(0) == 3

    def __call__(self, tensor):
        if random.uniform(0, 1) > self.p:
            return tensor
        alpha = torch.normal(mean=torch.zeros_like(self.eig_val)) * 0.1
        quatity = torch.mm(self.eig_val * alpha, self.eig_vec)
        tensor = tensor + quatity.view(3, 1, 1)
        return tensor


def build_transforms(height, width, transforms='random_flip', norm_mean=[0.485, 0.456, 0.406],
                     norm_std=[0.229, 0.224, 0.225], **kwargs):
    """Builds train and test transform functions.

    Args:
        height (int): target image height.
        width (int): target image width.
        transforms (str or list of str, optional): transformations applied to model training.
            Default is 'random_flip'.
        norm_mean (list): normalization mean values. Default is ImageNet means.
        norm_std (list): normalization standard deviation values. Default is
            ImageNet standard deviation values.
    """
    if transforms is None:
        transforms = []
    
    if isinstance(transforms, str):
        transforms = [transforms]

    if not isinstance(transforms, list):
        raise ValueError('transforms must be a list of strings, but found to be {}'.format(type(transforms)))
    
    if len(transforms) > 0:
        transforms = [t.lower() for t in transforms]
    
    normalize = Normalize(mean=norm_mean, std=norm_std)

    print('Building train transforms ...')
    transform_tr = []
    transform_tr += [Resize((height, width))]
    print('+ resize to {}x{}'.format(height, width))
    if 'random_flip' in transforms:
        print('+ random flip')
        transform_tr += [RandomHorizontalFlip()]
    if 'random_crop' in transforms:
        print('+ random crop (enlarge to {}x{} and ' \
              'crop {}x{})'.format(int(round(height*1.125)), int(round(width*1.125)), height, width))
        transform_tr += [Random2DTranslation(height, width)]
    if 'color_jitter' in transforms:
        print('+ color jitter')
        transform_tr += [ColorJitter(brightness=0.2, contrast=0.15, saturation=0, hue=0)]
    print('+ to torch tensor of range [0, 1]')
    transform_tr += [ToTensor()]
    print('+ normalization (mean={}, std={})'.format(norm_mean, norm_std))
    transform_tr += [normalize]
    if 'random_erase' in transforms:
        print('+ random erase')
        transform_tr += [RandomErasing()]
    transform_tr = Compose(transform_tr)

    print('Building test transforms ...')
    print('+ resize to {}x{}'.format(height, width))
    print('+ to torch tensor of range [0, 1]')
    print('+ normalization (mean={}, std={})'.format(norm_mean, norm_std))
    transform_te = Compose([
        Resize((height, width)),
        ToTensor(),
        normalize,
    ])

    return transform_tr, transform_te
