from django.core import signing
from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Box, Change, Customer, Destination, Part, SheetColor, normalize_code

class PartSerializer(serializers.ModelSerializer):
    customer = serializers.CharField(source='customer.name')
    destination = serializers.CharField(source='destination.name', allow_null=True)
    box = serializers.CharField(source='box.name', allow_null=True)
    sheet_color = serializers.CharField(source='sheet_color.name', allow_null=True)

    class Meta:
        model = Part
        fields = ['id', 'part_number', 'customer', 'destination', 'diameter', 'wall', 'wall_note', 'weight', 'box', 'std', 'sheet_color', 'reference_customer', 'reference_plant', 'active', 'version', 'created_at', 'updated_at']

class PartsPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

@api_view(['GET'])
def parts(request):
    qs = Part.objects.select_related('customer', 'destination', 'box', 'sheet_color').order_by('id')
    if request.query_params.get('q'):
        q = request.query_params['q'].strip()
        qs = qs.filter(Q(part_number__icontains=q) | Q(customer__name__icontains=q))
    if request.query_params.get('customer'):
        qs = qs.filter(customer__name__iexact=request.query_params['customer'])
    if request.query_params.get('active') in ('true', 'false'):
        qs = qs.filter(active=request.query_params['active'] == 'true')
    paginator = PartsPagination()
    return paginator.get_paginated_response(PartSerializer(paginator.paginate_queryset(qs, request), many=True).data)

@api_view(['GET'])
def exact(request):
    code = normalize_code(request.query_params.get('code', ''))
    if not code:
        return Response({'detail': 'Indique code.'}, status=400)
    matches = Part.objects.select_related('customer', 'destination', 'box', 'sheet_color').filter(normalized_number=code)
    if request.query_params.get('customer'):
        matches = matches.filter(customer__name__iexact=request.query_params['customer'])
    data = PartSerializer(matches, many=True).data
    return Response({'count': len(data), 'multiple': len(data) > 1, 'results': data})

@api_view(['GET'])
def part_detail(request, pk):
    try:
        part = Part.objects.select_related('customer', 'destination', 'box', 'sheet_color').get(pk=pk)
    except Part.DoesNotExist:
        return Response({'detail': 'No encontrada.'}, status=404)
    return Response(PartSerializer(part).data)

@api_view(['GET'])
def catalogs(request):
    return Response({key: list(model.objects.filter(active=True).values('id', 'name')) for key, model in [('customers', Customer), ('destinations', Destination), ('boxes', Box), ('sheet_colors', SheetColor)]})

@api_view(['GET'])
def changes(request):
    raw_cursor = request.query_params.get('cursor')
    if raw_cursor:
        try:
            last_id = int(signing.loads(raw_cursor, salt='catalog-changes'))
        except (signing.BadSignature, ValueError, TypeError):
            return Response({'detail': 'Cursor inválido.'}, status=400)
    else:
        last_id = 0
    try:
        limit = min(max(int(request.query_params.get('limit', 100)), 1), 200)
    except ValueError:
        return Response({'detail': 'Límite inválido.'}, status=400)
    selected = list(Change.objects.filter(pk__gt=last_id).select_related('part', 'part__customer', 'part__destination', 'part__box', 'part__sheet_color').order_by('pk')[:limit + 1])
    page = selected[:limit]
    cursor_id = page[-1].pk if page else last_id
    return Response({'results': [{'sequence': change.pk, 'operation': change.operation, 'part_id': str(change.part_id), 'part': change.after} for change in page], 'next_cursor': signing.dumps(cursor_id, salt='catalog-changes'), 'has_more': len(selected) > limit})

@api_view(['GET'])
def bootstrap(request):
    # Replay from genesis after the paged snapshot: this closes any gaps from concurrent writes.
    return Response({'parts_url': request.build_absolute_uri('/api/v1/parts/'), 'changes_cursor': signing.dumps(0, salt='catalog-changes'), 'procedure': 'Page through parts, then replay changes from this cursor until has_more is false.'})
