from django import forms  # ✅ forms import 추가!
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages

# ✅ 회원가입 폼 클래스 (Django Forms 사용)
class SignupForm(forms.Form):
    name = forms.CharField(max_length=150, label="이름")
    email = forms.EmailField(label="이메일")
    password = forms.CharField(widget=forms.PasswordInput, label="비밀번호")

def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)  # ✅ 폼 데이터 유지하도록 변경!

        if form.is_valid():
            username = form.cleaned_data.get('name')
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')

            # ✅ 이름 중복 검사
            if User.objects.filter(username=username).exists():
                messages.error(request, '이미 존재하는 이름입니다.')
                return render(request, 'accounts/signup.html', {'form': form})  # ✅ 입력값 유지!

            # ✅ 이메일 중복 검사
            if User.objects.filter(email=email).exists():
                messages.error(request, '이미 등록된 이메일입니다.')
                return render(request, 'accounts/signup.html', {'form': form})  # ✅ 입력값 유지!

            # ✅ 회원가입 진행
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)

            messages.success(request, f'{username}님, 가입을 환영합니다!')
            return redirect('/')  # 가입 성공 후 메인페이지 이동

    else:
        form = SignupForm()  # GET 요청일 때 빈 폼 생성

    return render(request, 'accounts/signup.html', {'form': form})  # ✅ 폼 데이터를 유지하면서 렌더링!


# 로그인 뷰
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'{user.username}님, 환영합니다!')
            else:
                messages.error(request, '비밀번호가 올바르지 않습니다.')
        except User.DoesNotExist:
            messages.error(request, '해당 이메일로 등록된 사용자가 없습니다.')

    return redirect('/')


# 로그아웃 뷰
def logout_view(request):
    logout(request)
    next_url = request.GET.get('next', '/')
    return redirect(next_url)