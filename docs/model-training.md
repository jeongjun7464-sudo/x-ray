# Model training

`PYTHONPATH=ml python ml/train.py --train train.csv --val val.csv --out ml/runs/v1`

DenseNet121 분류기, weighted sampler, 기본 증강, AdamW, ReduceLROnPlateau, early stopping, 고정 seed, best checkpoint 및 JSON 기록을 제공한다. `evaluate.py`는 Accuracy, 클래스별 Precision/Recall/F1, Macro F1, confusion matrix와 ECE를 출력한다. 실제 데이터 성능 수치는 아직 없으며 이 저장소는 어떠한 임상 성능도 주장하지 않는다. Grad-CAM은 모델의 마지막 convolution feature를 연결하는 후속 구현 항목이다.
