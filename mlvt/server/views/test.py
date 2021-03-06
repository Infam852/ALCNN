import os

import numpy as np
from PIL import Image
import torch

from connexion import request
from flask import flash, render_template
from werkzeug.utils import secure_filename

from mlvt.model.utils import get_resnet_test_transforms
from mlvt.server.actions.handlers import test
from mlvt.server.actions.main import Action
from mlvt.server.config import (USER_IMAGE_DIR, RELATIVE_USER_IMAGE_DIR,
                                CUT_STATIC_IDX)
from mlvt.server.exceptions import ImagesException
from mlvt.server.file_utils import load_json, purge_json_file, save_json
from mlvt.server.utils import test_image_counter
from mlvt.server.views.base import ActionView, ModelIOView


ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])


class TestView(ActionView, ModelIOView):
    def search(self, new_samples):
        self.init_cm()
        test_results = load_json(self.cm.get_test_results_file(),
                                 parse_keys_to=int)
        user_test = load_json(self.cm.get_last_user_test_path())
        if not test_results:
            flash('You have not tested your model yet', 'danger')
            return render_template('test.html.j2', results=[],
                                   user_test=user_test,
                                   show_results=False), 200
        # get last test result
        test_results = test_results[len(test_results) - 1]
        images = self._get_test_images(
            np.array(test_results['predictions']),
            np.array(test_results['paths']),
            increment=new_samples)
        return render_template('test.html.j2',
                               images=images,
                               user_test=user_test,
                               acc=test_results['acc'],
                               loss=test_results['loss'],
                               show_results=True,
                               path_start_idx=CUT_STATIC_IDX), 200

    def post(self):
        self.init_cm()
        if 'testImage' in request.files:
            uploaded = request.files['testImage']
            filename = secure_filename(uploaded.filename)
            if not self._allowed_file(filename):
                return f'Got unsupprted file type ({filename}),' \
                    f'supported extensions: ({ALLOWED_EXTENSIONS})', 400

            model = self.load_training_model()
            path = os.path.join(USER_IMAGE_DIR, filename)
            uploaded.save(path)
            img = Image.open(path).convert('RGB')
            # tranform image to tensor and normalize
            img = get_resnet_test_transforms()(img)
            frame = torch.unsqueeze(img, 0)
            prediction = model.predict(frame).flatten().cpu().numpy()
            labels = self._numeric_to_classname()
            user_test = {
                'label': labels[np.argmax(prediction)],
                'acc': round(max(prediction.tolist()), 3),
                'path': os.path.join(RELATIVE_USER_IMAGE_DIR, filename)
            }
            save_json(self.cm.get_last_user_test_path(), user_test)
            return user_test, 200

        self.run_action(Action.TEST, test)
        return 202

    def delete(self):
        self.init_cm()
        purge_json_file(self.cm.get_test_results_file())
        purge_json_file(self.cm.get_last_user_test_path())
        return 200

    def _get_test_images(self, predictions, paths, n_images=None,
                         increment=False):
        n_images = n_images or self.cm.get_test_n_outputs()

        if n_images > len(predictions):
            raise ImagesException("Not enough test results, "
                                  "please reset test history in settings")

        # lock gloabal counter
        with test_image_counter.get_lock():
            if test_image_counter.value + n_images >= len(predictions):
                test_image_counter.value = 0

            start_idx = test_image_counter.value
            idxs = range(start_idx, start_idx + n_images)
            if increment:
                test_image_counter.value += n_images

        predictions = predictions[idxs]
        paths = paths[idxs]
        images = []
        labels = self._numeric_to_classname()
        test_images = load_json(self.cm.get_test_annotations_path(),
                                parse_keys_to=int)

        for path, pred in zip(paths, predictions):
            images.append(
                {'path': path,
                 'label': labels[np.argmax(pred)],
                 'confidence': max(pred),
                 'good': True if path in test_images[np.argmax(pred)]
                    else False}
            )
        return images

    def _allowed_file(self, filename):
        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
