from django import forms
from .models import Hook

class HookForm(forms.ModelForm):
    class Meta:
        model = Hook
        fields = ['hooks_content', 'google_sheets_link', 'eleven_labs_api_key', 'voice_id', 'box_color', 'font_color']
        
        widgets = {
            'hooks_content': forms.ClearableFileInput(attrs={
                'id': 'hooks', 
                'accept': 'video/mp4,video/x-m4v,video/*', 
            }),
            'google_sheets_link': forms.URLInput(attrs={
                'id': 'google_link', 
                'placeholder': 'Paste URL Link'
            }),
            'eleven_labs_api_key': forms.TextInput(attrs={
                'id': 'api_key', 
                'placeholder': 'Paste API Key'
            }),
            'voice_id': forms.TextInput(attrs={
                'id': 'voice_id', 
                'placeholder': 'Enter Voice ID'
            }),
            'box_color': forms.TextInput(attrs={
                'type': 'color', 
                'class': 'color-input', 
                'value': '#485AFF',
                'id': 'boxcolor'
            }),
            'font_color': forms.TextInput(attrs={
                'type': 'color', 
                'class': 'color-input', 
                'value': '#FFFFFF',
                'id': 'fontcolor'
            }),
        }
