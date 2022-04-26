# !/usr/bin/env python
# -*- encoding: utf-8 -*-
# @File: yolov5_2_coco.py
# @Author: SWHL
# @Contact: liekkaskono@163.com
import argparse
import json
import shutil
from pathlib import Path

import cv2
from tqdm import tqdm


def read_txt(txt_path):
    with open(str(txt_path), 'r', encoding='utf-8') as f:
        data = list(map(lambda x: x.rstrip('\n'), f))
    return data


def mkdir(dir_path):
    Path(dir_path).mkdir(parents=True, exist_ok=True)


def verify_exists(file_path):
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f'The {file_path} is not exists!!!')


class YOLOV5ToCOCO(object):
    def __init__(self, dir_path):
        self.src_data = Path(dir_path)
        self.src = self.src_data.parent
        self.train_txt_path = self.src_data / 'train.txt'
        self.val_txt_path = self.src_data / 'val.txt'
        self.classes_path = self.src_data / 'classes.txt'

        # 文件存在性校验
        verify_exists(self.src_data / 'images')
        verify_exists(self.src_data / 'labels')
        verify_exists(self.train_txt_path)
        verify_exists(self.val_txt_path)
        verify_exists(self.classes_path)

        # 构建COCO格式目录
        self.dst = Path(self.src) / f"{Path(self.src_data).name}_COCO_format"
        self.coco_train = "train2017"
        self.coco_val = "val2017"
        self.coco_annotation = "annotations"
        self.coco_train_json = self.dst / self.coco_annotation / \
            f'instances_{self.coco_train}.json'
        self.coco_val_json = self.dst / self.coco_annotation / \
            f'instances_{self.coco_val}.json'

        mkdir(self.dst)
        mkdir(self.dst / self.coco_train)
        mkdir(self.dst / self.coco_val)
        mkdir(self.dst / self.coco_annotation)

        # 构建json内容结构
        self.type = 'instances'
        self.categories = []
        self.annotation_id = 1

        # 读取类别数
        self._get_category()

        self.info = {
            'year': 2021,
            'version': '1.0',
            'description': 'For object detection',
            'date_created': '2021',
        }

        self.licenses = [{
            'id': 1,
            'name': 'Apache License v2.0',
            'url': 'https://github.com/RapidAI/YOLO2COCO/LICENSE',
        }]

    def _get_category(self):
        class_list = read_txt(self.classes_path)
        for i, category in enumerate(class_list, 1):
            self.categories.append({
                'supercategory': category,
                'id': i,
                'name': category,
            })

    def generate(self):
        self.train_files = read_txt(self.train_txt_path)
        self.valid_files = read_txt(self.val_txt_path)

        train_dest_dir = Path(self.dst) / self.coco_train
        self.gen_dataset(self.train_files, train_dest_dir,
                         self.coco_train_json, mode='train')

        val_dest_dir = Path(self.dst) / self.coco_val
        self.gen_dataset(self.valid_files, val_dest_dir,
                         self.coco_val_json, mode='val')

        print(f"The output directory is: {str(self.dst)}")

    def gen_dataset(self, img_paths, target_img_path, target_json, mode):
        """
        https://cocodataset.org/#format-data

        """
        images = []
        annotations = []
        for img_id, img_path in enumerate(tqdm(img_paths, desc=mode), 1):
            img_path = Path(img_path)

            verify_exists(img_path)

            label_path = str(img_path.parent.parent
                             / 'labels' / f'{img_path.stem}.txt')

            imgsrc = cv2.imread(str(img_path))
            height, width = imgsrc.shape[:2]

            dest_file_name = f'{img_id:012d}.jpg'
            save_img_path = target_img_path / dest_file_name

            if img_path.suffix.lower() == ".jpg":
                shutil.copyfile(img_path, save_img_path)
            else:
                cv2.imwrite(str(save_img_path), imgsrc)

            images.append({
                'date_captured': '2021',
                'file_name': dest_file_name,
                'id': img_id,
                'height': height,
                'width': width,
            })

            if Path(label_path).exists():
                new_anno = self.read_annotation(label_path, img_id,
                                                height, width)
                if len(new_anno) > 0:
                    annotations.extend(new_anno)
                else:
                    # raise ValueError(f'{label_path} is empty')
                    pass
            else:
                raise FileNotFoundError(f'{label_path} not exists')

        json_data = {
            'info': self.info,
            'images': images,
            'licenses': self.licenses,
            'type': self.type,
            'annotations': annotations,
            'categories': self.categories,
        }
        with open(target_json, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False)

    def read_annotation(self, txt_file, img_id, height, width):
        annotation = []
        all_info = read_txt(txt_file)
        for label_info in all_info:
            # 遍历一张图中不同标注对象
            label_info = label_info.split(" ")
            if len(label_info) < 5:
                continue

            category_id, vertex_info = label_info[0], label_info[1:]
            segmentation, bbox, area = self._get_annotation(vertex_info,
                                                            height, width)
            annotation.append({
                'segmentation': segmentation,
                'area': area,
                'iscrowd': 0,
                'image_id': img_id,
                'bbox': bbox,
                'category_id': int(category_id)+1,
                'id': self.annotation_id,
            })
            self.annotation_id += 1
        return annotation

    @staticmethod
    def _get_annotation(vertex_info, height, width):
        cx, cy, w, h = [float(i) for i in vertex_info]

        cx = cx * width
        cy = cy * height
        box_w = w * width
        box_h = h * height

        # left top
        x0 = max(cx - box_w / 2, 0)
        y0 = max(cy - box_h / 2, 0)

        # right bottomt
        x1 = min(x0 + box_w, width)
        y1 = min(y0 + box_h, height)

        segmentation = [[x0, y0, x1, y0, x1, y1, x0, y1]]
        bbox = [x0, y0, box_w, box_h]
        area = box_w * box_h
        return segmentation, bbox, area


if __name__ == "__main__":
    parser = argparse.ArgumentParser('Datasets converter from YOLOV5 to COCO')
    parser.add_argument('--dir_path', type=str,
                        default='datasets/YOLOV5',
                        help='Dataset root path')
    args = parser.parse_args()

    converter = YOLOV5ToCOCO(args.dir_path)
    converter.generate()
