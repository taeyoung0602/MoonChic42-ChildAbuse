
import os
import json
import joblib
import csv
import pandas as pd
from django.conf import settings
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from .models import ChildObservation, PredictionHistory
from .forms import ObservationForm, AbusePredictionForm



# 0. 누적 테이블 초기화
@require_POST
def reset_dashboard(request):
    ChildObservation.objects.all().delete()
    PredictionHistory.objects.all().delete()
    return redirect('home')

# ✅ 1. CSV 파일 경로 설정
CSV_PATH = os.path.join(settings.BASE_DIR, 'childabuse', 'data', '어린이집_더미데이터_확장본_250326.csv')
DATA_PATH = os.path.join(settings.BASE_DIR, 'childabuse', 'data', '어린이집_더미데이터_확장본_250326.csv')
MODEL_PATH = os.path.join(settings.BASE_DIR, 'childabuse', 'model', 'random_forest_model.pkl')
META_PATH = os.path.join(settings.BASE_DIR, 'childabuse', 'model', 'model_meta.json')

# ✅ 모델 로드
model_bundle = joblib.load(MODEL_PATH)
model = model_bundle['model']
accuracy = round(model_bundle['accuracy'] * 100, 2)
model_accuracy = f"정확도: {round(model_bundle['accuracy'] * 100, 2)}%"

df = pd.read_csv(CSV_PATH)

# 문자형 → 수치형 매핑
df = df.replace({
    '성별': {'남': 0, '남아': 0, '여': 1, '여아': 1},
    '출석패턴': {'정상': 0, '자주결석': 1, '불규칙': 2},
    '부정언어표현': {'낮음': 0, '중간': 1, '높음': 2},
    '보호자공격성': {'없음': 0, '약함': 1, '강함': 2},
    '신체접촉반응': {'선호': 0, '중립': 1, '회피': 2, '공포': 3},
    '소득수준': {'낮음': 0, '중간': 1, '높음': 2},
    '보호자정서상태': {'안정': 0, '우울': 1, '불안': 2}
})

# 과거신고이력은 별도로 강제 처리
df['과거신고이력'] = df['과거신고이력'].replace({'없음': 0, '있음': 1}).astype(int)

# 오류 방지용 형변환
df = df.infer_objects(copy=False)

# 평균 계산
mean_values = df[[
    '나이', '성별', '출석패턴', '부정언어표현',
    '보호자공격성', '신체접촉반응', '형제자매수',
    '소득수준', '보호자정서상태'
]].mean().round(2).tolist()


# ✅ 매핑 딕셔너리
GENDER_MAP = {'남아': 0, '여아': 1}
ATTENDANCE_MAP = {'정상': 0, '자주결석': 1, '불규칙': 2}
NEG_LANG_MAP = {'낮음': 0, '중간': 1, '높음': 2}
AGGRESSION_MAP = {'없음': 0, '약함': 1, '강함': 2}
REACTION_MAP = {'선호': 0, '중립': 1, '회피': 2, '공포': 3}
INCOME_MAP = {'낮음': 0, '중간': 1, '높음': 2}
EMOTION_MAP = {'안정': 0, '우울': 1, '불안': 2}


# ✅ 예측 함수
def predict_danger(instance):
    input_df = pd.DataFrame([{
        '나이': instance.age,
        '성별': GENDER_MAP.get(instance.gender, 0),
        '출석패턴': ATTENDANCE_MAP.get(instance.attendance, 0),
        '부정언어표현': NEG_LANG_MAP.get(instance.negative_language, 1),
        '보호자공격성': AGGRESSION_MAP.get(instance.parental_aggression, 1),
        '신체접촉반응': REACTION_MAP.get(instance.contact_reaction, 1),
        '형제자매수': instance.sibling,
        '소득수준': INCOME_MAP.get(instance.income_level, 1),
        '보호자정서상태': EMOTION_MAP.get(instance.emotional_state, 0)
    }])
    prob = model.predict_proba(input_df)[0][1]
    return (prob >= 0.5), round(prob * 100, 2)


def predict_danger_extended(data):
    input_df = pd.DataFrame([{
        '나이': int(data.get('age', 0)),
        '성별': GENDER_MAP.get(data.get('gender'), 0),
        '출석패턴': ATTENDANCE_MAP.get(data.get('attendance'), 0),
        '부정언어표현': NEG_LANG_MAP.get(data.get('negative_language'), 1),
        '보호자공격성': AGGRESSION_MAP.get(data.get('parental_aggression'), 1),
        '신체접촉반응': REACTION_MAP.get(data.get('contact_reaction'), 1),
        '형제자매수': int(data.get('sibling', 0)),
        '소득수준': INCOME_MAP.get(data.get('income_level'), 1),
        '보호자정서상태': EMOTION_MAP.get(data.get('emotional_state'), 0)
    }])
    prediction = model.predict(input_df)[0]
    return prediction, input_df.iloc[0].tolist()


# ✅ 홈
def home_view(request):
    form = ObservationForm(request.POST or None)
    
    if request.method == 'POST':
        print("📩 폼 제출 감지됨")
        print("✅ 유효성 검사 통과 여부:", form.is_valid())
        print("🚨 에러:", form.errors)

        if form.is_valid():
            instance = form.save(commit=False)
            is_danger, prob = predict_danger(instance)
            instance.is_danger = is_danger
            instance.save()

            PredictionHistory.objects.create(
                child_name=instance.child_name,
                predicted_result="위험" if is_danger else "정상",
                predicted_prob=prob
            )
            return redirect('home')

    # 👇 예측 확률 딕셔너리 구성 (이름별 가장 최신 값만)
    history_dict = {}
    for history in PredictionHistory.objects.all().order_by('-id'):
        if history.child_name not in history_dict:
            history_dict[history.child_name] = history.predicted_prob

    # ✅ 템플릿에 전달할 context
    context = {
        'form': form,
        'observation_list': ChildObservation.objects.all().order_by('-observation_date'),
        'history_dict': history_dict,
        'total_kids': len(df),
        'danger_kids': int(df['과거신고이력'].sum()),
        'last_report_date': f"정확도: {accuracy}%"
    }

    return render(request, 'main_home.html', context)



# ✅ 단건 예측 (/predict)
def predict_view(request):
    form = AbusePredictionForm(request.POST or None)
    context = {'form': form, 'range_0_5': range(6)}

    if request.method == 'POST' and form.is_valid():
        data = request.POST.dict()
        prediction, input_values = predict_danger_extended(data)
        is_danger = prediction == 1

        instance = ChildObservation(
            child_name=data.get('child_name'),
            age=int(data.get('age')),
            gender=data.get('gender'),
            attendance=data.get('attendance'),
            negative_language=data.get('negative_language'),
            parental_aggression=data.get('parental_aggression'),
            contact_reaction=data.get('contact_reaction'),
            sibling=int(data.get('sibling', 0)),
            income_level=data.get('income_level'),
            emotional_state=data.get('emotional_state'),
            is_danger=is_danger
        )
        instance.save()

        PredictionHistory.objects.create(
            child_name=instance.child_name,
            predicted_result="위험" if is_danger else "정상"
        )

        context.update({
            'result': f"예측 결과: {'위험' if is_danger else '정상'}",
            'accuracy': f"정확도: {accuracy}%",
            'input_values': input_values,
            'feature_means': mean_values
        })
    elif request.method == 'POST':
        context['result'] = "❌ 유효하지 않은 입력입니다."

    return render(request, 'form.html', context)


# ✅ 입력 폼 및 업로드 뷰들
def main_index(request):
    return render(request, 'index.html')

def single_form_view(request):
    form = AbusePredictionForm()  # 🔥 폼 객체 생성
    context = {'form': form, 'range_0_5': range(6)}  # 🔥 context에 form 전달
    return render(request, 'form.html', context)

    
def bulk_form_view(request):
    # ✅ 위험 아동 CSV 저장 요청
    if request.method == 'POST' and request.POST.get('export_risk_only') == 'true':
        risk_data = request.session.get('risk_results', [])

        # 응답으로 CSV 반환
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="위험_아동_예측결과.csv"'

        writer = csv.DictWriter(response, fieldnames=[
            '나이', '성별', '출석', '부정언어표현', '보호자공격성',
            '신체접촉반응', '형제자매수', '소득수준', '보호자정서상태', '예측결과'
        ])
        writer.writeheader()
        for row in risk_data:
            writer.writerow(row)

        return response

    # ✅ CSV 파일 업로드 처리
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        df = pd.read_csv(csv_file)

        results = []
        risk_only = []  # 위험 아동만 따로 저장

        for _, row in df.iterrows():
            data = {
                '나이': row.get('나이'),
                '성별': row.get('성별'),
                '출석': row.get('출석'),
                '부정언어표현': row.get('부정언어표현'),
                '보호자공격성': row.get('보호자공격성'),
                '신체접촉반응': row.get('신체접촉반응', '중립'),
                '형제자매수': row.get('형제자매수', 0),
                '소득수준': row.get('소득수준', '중간'),
                '보호자정서상태': row.get('보호자정서상태', '안정')
            }

            # 예측 수행
            pred_input = {
                'age': data['나이'],
                'gender': data['성별'],
                'attendance': data['출석'],
                'negative_language': data['부정언어표현'],
                'parental_aggression': data['보호자공격성'],
                'contact_reaction': data['신체접촉반응'],
                'sibling': data['형제자매수'],
                'income_level': data['소득수준'],
                'emotional_state': data['보호자정서상태']
            }
            prediction, _ = predict_danger_extended(pred_input)
            result_text = "가정폭력 위험이 있습니다" if prediction else "정상"

            row_result = {**data, '예측결과': result_text}
            results.append(row_result)

            if result_text == "가정폭력 위험이 있습니다":
                risk_only.append(row_result)

        # 위험 결과를 세션에 저장
        request.session['risk_results'] = risk_only

        return render(request, 'bulk_form.html', {
            'results': results,
            'filename': csv_file.name,
            'results_json': json.dumps(results, ensure_ascii=False),
            'accuracy': accuracy
        })

    return render(request, 'bulk_form.html')


def export_filtered_csv(request):
    if request.method == 'POST':
        result_data = json.loads(request.POST.get('result_data', '[]'))
        filtered_data = [row for row in result_data if row.get('예측결과') == '가정폭력 위험이 있습니다']

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=filtered_results.csv'

        writer = csv.DictWriter(response, fieldnames=filtered_data[0].keys())
        writer.writeheader()
        writer.writerows(filtered_data)

        return response
    

def csv_upload_view(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        df = pd.read_csv(csv_file)
        for _, row in df.iterrows():
            ChildObservation.objects.create(
                child_name=row['아동이름'],
                age=row['나이'],
                gender=row['성별'],
                attendance=row['출석'],
                negative_language=row['부정언어표현'],
                parental_aggression=row['보호자공격성'],
                contact_reaction=row.get('신체접촉반응', '중립'),
                sibling=row.get('형제자매수', 0),
                income_level=row.get('소득수준', '중간'),
                emotional_state=row.get('보호자정서상태', '안정'),
                is_danger=row.get('is_danger', False),
            )
        return redirect('home')
    return render(request, 'bulk_form.html')

