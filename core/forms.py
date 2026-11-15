from django import forms
from django.contrib.auth import get_user_model
from .models import Project, Dataset
User = get_user_model()

class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]
    def clean_email(self): return self.cleaned_data["email"].strip().lower()
    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("confirm_password"): self.add_error("confirm_password", "Passwords do not match.")
        return data
    def save(self, commit=True):
        user = super().save(commit=False); user.set_password(self.cleaned_data["password"])
        if commit: user.save()
        return user

class ProjectForm(forms.ModelForm):
    class Meta: model = Project; fields = ["name"]
    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name: raise forms.ValidationError("Enter a project name.")
        return name

class AvatarForm(forms.ModelForm):
    class Meta: model = User; fields = ["avatar"]

class DatasetForm(forms.ModelForm):
    class Meta: model = Dataset; fields = ["csv_file"]
    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"): raise forms.ValidationError("Upload a CSV file.")
        if f.size > 10 * 1024 * 1024: raise forms.ValidationError("Maximum file size is 10 MB.")
        return f
