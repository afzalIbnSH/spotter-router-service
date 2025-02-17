from django.shortcuts import render
from django.http import JsonResponse

def get_optimal_route(request):
    return JsonResponse({"place": "holder!"})
