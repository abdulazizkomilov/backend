from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404

from datetime import timedelta
from collections import Counter
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes

from account.models import User, FriendshipRequest
from account.serializers import UserSerializer
from notification.utils import create_notification

from .forms import PostForm, AttachmentForm
from .models import Post, Like, Comment, Trend
from .serializers import PostSerializer, PostDetailSerializer, CommentSerializer, TrendSerializer


@api_view(['GET'])
def post_list(request):
    posts = Post.objects.all()

    trend = request.GET.get('trend', '')

    if trend:
        posts = posts.filter(body__icontains='#' +
                             trend).filter(is_private=False)

    serializer = PostSerializer(posts, many=True)

    return JsonResponse(serializer.data, safe=False)


@api_view(['GET'])
def post_detail(request, pk):
    user_ids = [request.user.id]

    if request.user.is_authenticated:
        for user in request.user.friends.all():
            user_ids.append(user.id)

    post = Post.objects.filter(Q(created_by_id__in=list(
        user_ids)) | Q(is_private=False)).get(pk=pk)

    return JsonResponse({
        'post': PostDetailSerializer(post).data
    })


@api_view(['GET'])
def post_list_profile(request, id):
    user = User.objects.get(pk=id)
    posts = Post.objects.filter(created_by_id=id)

    if not request.user in user.friends.all():
        posts = posts.filter(is_private=False)

    posts_serializer = PostSerializer(posts, many=True)
    user_serializer = UserSerializer(user)

    can_send_friendship_request = True

    if request.user in user.friends.all():
        can_send_friendship_request = False

    check1 = FriendshipRequest.objects.filter(
        created_for=request.user).filter(created_by=user)
    check2 = FriendshipRequest.objects.filter(
        created_for=user).filter(created_by=request.user)

    if check1 or check2:
        can_send_friendship_request = False

    return JsonResponse({
        'posts': posts_serializer.data,
        'user': user_serializer.data,
        'can_send_friendship_request': can_send_friendship_request
    }, safe=False)


@api_view(['GET'])
def favourite_list(request, id):
    user = User.objects.get(pk=id)
    posts = Post.objects.filter(favourites=user)
    posts_serializer = PostSerializer(posts, many=True)

    return JsonResponse(posts_serializer.data, safe=False)


@api_view(['GET'])
def get_me(request):
    user = request.user

    user_serializer = UserSerializer(user)
    return JsonResponse({
        'user': user_serializer.data,
    }, safe=False)


def extract_hashtags(text, trends):
    for word in text.split():
        if word[0] == '#':
            trends.append(word[1:])

    return trends


@api_view(['POST'])
def post_create(request):
    form = PostForm(request.POST)
    attachment = None
    attachment_form = AttachmentForm(request.POST, request.FILES)

    if attachment_form.is_valid():
        attachment = attachment_form.save(commit=False)
        attachment.created_by = request.user
        attachment.save()

    if form.is_valid():
        post = form.save(commit=False)
        post.created_by = request.user
        post.save()

        if attachment:
            post.attachments.add(attachment)

        user = request.user
        user.posts_count = user.posts_count + 1
        user.save()

        for trend in Trend.objects.all():
            trend.delete()

        trends = []
        this_hour = timezone.now().replace(minute=0, second=0, microsecond=0)
        twenty_four_hours = this_hour - timedelta(hours=24)

        for post in Post.objects.filter(created_at__gte=twenty_four_hours).filter(is_private=False):
            extract_hashtags(post.body, trends)

        for trend in Counter(trends).most_common(10):
            Trend.objects.create(hashtag=trend[0], occurences=trend[1])

        serializer = PostSerializer(post)

        return JsonResponse(serializer.data, safe=False)
    else:
        return JsonResponse({'error': 'add somehting here later!...'})


@api_view(['POST'])
def post_like(request, pk):
    post = Post.objects.get(pk=pk)

    if not post.likes.filter(created_by=request.user):
        like = Like.objects.create(created_by=request.user)

        post = Post.objects.get(pk=pk)
        post.likes_count = post.likes_count + 1
        post.likes.add(like)
        post.save()

        notification = create_notification(
            request, 'post_like', post_id=post.id)

        return JsonResponse({'message': 'like created'})
    else:
        return JsonResponse({'message': 'post already liked'})


@api_view(['POST'])
def post_create_comment(request, pk):
    comment = Comment.objects.create(
        body=request.data.get('body'), created_by=request.user)

    post = Post.objects.get(pk=pk)
    post.comments.add(comment)
    post.comments_count = post.comments_count + 1
    post.save()

    notification = create_notification(
        request, 'post_comment', post_id=post.id)

    serializer = CommentSerializer(comment)

    return JsonResponse(serializer.data, safe=False)


@api_view(['DELETE'])
def post_delete(request, pk):
    post = Post.objects.filter(created_by=request.user).get(pk=pk)
    post.delete()

    return JsonResponse({'message': 'post deleted'})


@api_view(['POST'])
def post_report(request, pk):
    post = Post.objects.get(pk=pk)
    post.reported_by_users.add(request.user)
    post.save()

    return JsonResponse({'message': 'post reported'})


@api_view(['GET'])
def get_trends(request):
    serializer = TrendSerializer(Trend.objects.all(), many=True)

    return JsonResponse(serializer.data, safe=False)


@api_view(['POST'])
def favourite_add(request, pk):
    post = get_object_or_404(Post, id=pk)
    if post.favourites.filter(id=request.user.id).exists():
        post.favourites.remove(request.user)
        message = 'removed'
    else:
        post.favourites.add(request.user)
        message = 'saved'
    return JsonResponse({'message': f'post {message}'})
