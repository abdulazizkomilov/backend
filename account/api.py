from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import send_mail
from django.http import HttpResponse
from django.http import JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from notification.utils import create_notification

from .forms import ProfileForm, SignupForm
from .models import User, FriendshipRequest
from .serializers import UserSerializer, FriendshipRequestSerializer

import random
from infobip_channels.sms.channel import SMSChannel

BASE_URL = "https://ejv5qn.api.infobip.com"
API_KEY = "505755f17769e60ae5b42f0595add8a2-fed04b6a-f25e-4bff-bc48-3ec9fef8c73a"
RECIPIENT = "998931159963"


class Code:
    def __init__(self):
        self.code = None

    def __repr__(self):
        return str(self.code)

    def generate(self):
        self.code = random.randint(10000, 99999)

    def get_code(self):
        return str(self.code)


a = Code()


@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def signup(request):
    data = request.data
    message = 'success'
    a.generate()
    form = SignupForm({
        'email': data.get('email'),
        'name': data.get('name'),
        'phone': data.get('phone'),
        'password1': data.get('password1'),
        'password2': data.get('password2'),
    })

    if form.is_valid():
        channel = SMSChannel.from_auth_params(
            {"base_url": BASE_URL, "api_key": API_KEY})
        sms_response = channel.send_sms_message(
            {
                "messages": [
                    {
                        "destinations": [{"to": data.get('phone')}],
                        "text": f"Your activate code: {a}",
                    }
                ]
            }
        )
        query_parameters = {"limit": 10}
        delivery_reports = channel.get_outbound_sms_delivery_reports(
            query_parameters)
        print(delivery_reports)
        user = form.save()
        user.code = a
        user.is_active = False
        user.save()
    else:
        message = form.errors.as_json()

    print(message)

    return JsonResponse({'message': message}, safe=False)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def verify(request):
    print(a.get_code())
    form = {'code': request.data.get('code')}
    code = form['code']

    if str(code) == a.get_code():
        user = User.objects.get(code=str(code))
        user.is_active = True
        user.save()
        a.generate()
        print(a.get_code())
        return JsonResponse({'message': 'success'}, safe=False)
    else:
        return JsonResponse({'message': 'bad'}, safe=False)


@api_view(['GET'])
def get_users(request):
    users = User.objects.all()

    users_serializer = UserSerializer(users, many=True)
    return JsonResponse({
        'all_users': users_serializer.data
    })


@api_view(['GET'])
def me(request):
    return JsonResponse({
        'id': request.user.id,
        'name': request.user.name,
        'email': request.user.email,
        'avatar': request.user.get_avatar()
    })


@api_view(['GET'])
def friends(request, pk):
    user = User.objects.get(pk=pk)
    requests = []

    if user == request.user:
        requests = FriendshipRequest.objects.filter(
            created_for=request.user, status=FriendshipRequest.SENT)
        requests = FriendshipRequestSerializer(requests, many=True)
        requests = requests.data

    friends = user.friends.all()

    return JsonResponse({
        'user': UserSerializer(user).data,
        'friends': UserSerializer(friends, many=True).data,
        'requests': requests
    }, safe=False)


@api_view(['GET'])
def my_friendship_suggestions(request):
    serializer = UserSerializer(
        request.user.people_you_may_know.all(), many=True)

    return JsonResponse(serializer.data, safe=False)


@api_view(['POST'])
def editprofile(request):
    user = request.user
    email = request.data.get('email')

    if User.objects.exclude(id=user.id).filter(email=email).exists():
        return JsonResponse({'message': 'email already exists'})
    else:
        form = ProfileForm(request.POST, request.FILES, instance=user)

        if form.is_valid():
            form.save()

        serializer = UserSerializer(user)

        return JsonResponse({'message': 'information updated', 'user': serializer.data})


@api_view(['POST'])
def editpassword(request):
    user = request.user

    form = PasswordChangeForm(data=request.POST, user=user)

    if form.is_valid():
        form.save()

        return JsonResponse({'message': 'success'})
    else:
        return JsonResponse({'message': form.errors.as_json()}, safe=False)


@api_view(['POST'])
def send_friendship_request(request, pk):
    user = User.objects.get(pk=pk)

    check1 = FriendshipRequest.objects.filter(
        created_for=request.user).filter(created_by=user)
    check2 = FriendshipRequest.objects.filter(
        created_for=user).filter(created_by=request.user)

    if not check1 or not check2:
        friendrequest = FriendshipRequest.objects.create(
            created_for=user, created_by=request.user)

        notification = create_notification(
            request, 'new_friendrequest', friendrequest_id=friendrequest.id)

        return JsonResponse({'message': 'friendship request created'})
    else:
        return JsonResponse({'message': 'request already sent'})


@api_view(['POST'])
def handle_request(request, pk, status):
    user = User.objects.get(pk=pk)
    friendship_request = FriendshipRequest.objects.filter(
        created_for=request.user).get(created_by=user)
    friendship_request.status = status
    friendship_request.save()

    user.friends.add(request.user)
    user.friends_count = user.friends_count + 1
    user.save()

    request_user = request.user
    request_user.friends_count = request_user.friends_count + 1
    request_user.save()

    notification = create_notification(
        request, 'accepted_friendrequest', friendrequest_id=friendship_request.id)

    return JsonResponse({'message': 'friendship request updated'})
