from django.contrib.auth.mixins import LoginRequiredMixin,UserPassesTestMixin
from django.contrib.auth.views import (
LoginView,LogoutView,PasswordChangeView,PasswordChangeDoneView,
PasswordResetView,PasswordResetDoneView,PasswordResetConfirmView,PasswordResetCompleteView
)
from django.views import generic
from .forms import (
    LoginForm, UserCreateForm,UserUpdateForm,MyPasswordChangeForm,
    MyPasswordResetForm,MySetPasswordForm,EmailChangeForm
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.core.signing import BadSignature,SignatureExpired,loads,dumps
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import redirect, resolve_url
from django.template.loader import get_template

from django.urls import reverse_lazy
from django.core.mail import send_mail




# Create your views here.
User=get_user_model()



class Top(generic.TemplateView):
    template_name = 'userapp/top.html'


class Login(LoginView):
    """ログインページ"""
    form_class = LoginForm
    template_name = 'userapp/login.html'


class Logout(LoginRequiredMixin,LogoutView):
    """ログアウトページ"""
    template_name = 'userapp/top.html'





class UserCreate(generic.CreateView):
    """ユーザー仮登録"""
    template_name = 'userapp/user_create.html'
    form_class = UserCreateForm

    def form_valid(self,form):
        """仮登録と本登録用のメールの発行"""
        #仮登録と本登録の切り替えは、is_active属性を使うと簡単です。
        #退会処理も、is_activeをFalseにするだけにしておくと捗ります。
        user=form.save(commit=False)
        user.is_active=False
        user.save()

        #アクティベーションURLの送付
        current_site=get_current_site(self.request)
        domain=current_site.domain
        context={
            'protocol':self.request.scheme,
            'domain':domain,
            'token':dumps(user.pk),
            'user':user,
        }

        subject_template=get_template('userapp/mail_template/create/subject.txt')
        subject=subject_template.render(context)

        message_template=get_template('userapp/mail_template/create/message.txt')
        message=message_template.render(context)

        user.email_user(subject,message)
        return redirect('userapp:user_create_done')

class UserCreateDone(generic.TemplateView):
    """ユーザー仮登録したよ"""
    template_name = 'userapp/user_create_done.html'


class UserCreateComplete(generic.TemplateView):
    """メール内URLアクセス後のユーザー本登録"""
    template_name = 'userapp/user_create_complete.html'
    timeout_seconds=getattr(settings,'ACTIVATION_TIMEOUT_SECONDS',60*60*24)

    def get(self,request,**kwargs):
        """tokenが正しければ本登録"""
        token=kwargs.get('token')
        try:
            user_pk=loads(token,max_age=self.timeout_seconds)

        #期限切れ
        except SignatureExpired:
            return HttpResponseBadRequest()

        #tokenが間違っている
        except BadSignature:
            return HttpResponseBadRequest()

        #tokenは問題なし
        else:
            try:
                user=User.objects.get(pk=user_pk)
            except User.DoesNotExist:
                return HttpResponseBadRequest()
            else:
                if not user.is_active:
                    # 問題なければ本登録する
                    user.is_active=True
                    user.save()
                    return super().get(request,**kwargs)

        return HttpResponseBadRequest()


class OnlyYouMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        user=self.request.user
        return user.pk==self.kwargs['pk'] or user.is_superuser


class UserDetail(OnlyYouMixin,generic.DetailView):
    model = User
    template_name = 'userapp/user_detail.html'


class UserUpdate(OnlyYouMixin,generic.UpdateView):
    model = User
    template_name = 'userapp/user_form.html'
    form_class = UserUpdateForm

    def get_success_url(self):
        return resolve_url('userapp:user_detail',pk=self.kwargs['pk'])



class PasswordChange(PasswordChangeView):
    """パスワード変更ビュー"""
    form_class = MyPasswordChangeForm
    success_url = reverse_lazy('userapp:password_change_done')
    template_name = 'userapp/password_change.html'


class PasswordChangeDone(PasswordChangeDoneView):
    """パスワード変更しました"""
    template_name = 'userapp/password_change_done.html'



class PasswordReset(PasswordResetView):
    """パスワード変更用URLの送付ページ"""
    subject_template_name = 'userapp/mail_template/password_reset/subject.txt'
    email_template_name = 'userapp/mail_template/password_reset/message.txt'
    template_name = 'userapp/password_reset_form.html'
    form_class = MyPasswordResetForm
    success_url = reverse_lazy('userapp:password_reset_done')


class PasswordResetDone(PasswordResetDoneView):
    """パスワード変更用URLを送りましたページ"""
    template_name = 'userapp/password_reset_done.html'

class PasswordResetConfirm(PasswordResetConfirmView):
    """新パスワード入力ページ"""
    form_class = MySetPasswordForm
    success_url = reverse_lazy('userapp:password_reset_complete')
    template_name = 'userapp/password_reset_confirm.html'

class PasswordResetComplete(PasswordResetCompleteView):
    """新パスワード設定しましたページ"""
    template_name = 'userapp/password_reset_complete.html'



class EmailChange(LoginRequiredMixin, generic.FormView):
    """メールアドレスの変更"""
    template_name = 'userapp/email_change_form.html'
    form_class = EmailChangeForm

    def form_valid(self, form):
        user = self.request.user
        new_email = form.cleaned_data['email']

        # URLの送付
        current_site = get_current_site(self.request)
        domain = current_site.domain
        context = {
            'protocol': 'https' if self.request.is_secure() else 'http',
            'domain': domain,
            'token': dumps(new_email),
            'user': user,
        }

        subject_template = get_template('userapp/mail_template/email_change/subject.txt')
        subject = subject_template.render(context)

        message_template = get_template('userapp/mail_template/email_change/message.txt')
        message = message_template.render(context)
        send_mail(subject, message, None, [new_email])

        return redirect('userapp:email_change_done')



class EmailChangeDone(LoginRequiredMixin,generic.TemplateView):
    """メールアドレスの変更メールを送ったよ"""
    template_name = 'userapp/email_change_done.html'


class EmailChangeComplete(LoginRequiredMixin, generic.TemplateView):
    """リンクを踏んだ後に呼ばれるメアド変更ビュー"""
    template_name = 'userapp/email_change_done.html'
    timeout_seconds = getattr(settings, 'ACTIVATION_TIMEOUT_SECONDS', 60*60*24)  # デフォルトでは1日以内

    def get(self, request, **kwargs):
        token = kwargs.get('token')
        try:
            new_email = loads(token, max_age=self.timeout_seconds)

        # 期限切れ
        except SignatureExpired:
            return HttpResponseBadRequest()

        # tokenが間違っている
        except BadSignature:
            return HttpResponseBadRequest()

        # tokenは問題なし
        else:
            User.objects.filter(email=new_email, is_active=False).delete()
            request.user.email = new_email
            request.user.save()
            return super().get(request, **kwargs)
