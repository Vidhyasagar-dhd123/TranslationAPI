from django.shortcuts import render
from django.apps import apps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def translate_text(request):
    translator = apps.get_app_config('translation').translator
    print("\nGET request received",request.GET.get('text', ''),)
    input_text = request.GET.get('text', '')
    target_lang = request.GET.get('target_lang', 'hin_Deva')  # default to Hindi
    source_lang = request.GET.get('source_lang', 'eng_Latn')  # default to English
    translated_text = translator.translate_paragraph(input_text, src_lang=source_lang, tgt_lang=target_lang)
    print("\nTranslated Text:",translated_text)
    return JsonResponse({'translated_text': translated_text})