from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.db.models import Q
from .forms import UserRegisterForm, UserLoginForm, PostForm, CommentForm, UserProfileForm, MessageForm
from .models import Post, Like, Comment, CommentLike, UserProfile, Favorite, Message, Category, Product


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f"Аккаунт {username} успешно создан")
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, "app/register.html", {'form': form})


def user_login(request):
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, "Неправильное имя пользователя или пароль!")

    else:
        form = UserLoginForm()
    return render(request, 'app/login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('login')


@login_required
def home(request):
    # Получаем все объекты Post из базы данных
    posts = Post.objects.all()

    # Передаем список posts в шаблон home.html через контекст
    context = {
        'posts': posts,  # 'posts' - это имя переменной, которое будет доступно в шаблоне
    }
    return render(request, 'app/home.html', context)


@login_required
def post_detail(request, post_id):
    # Получаем конкретный пост по ID или возвращаем 404, если не найден
    post = get_object_or_404(Post, id=post_id)
    # Проверяем, поставил ли текущий пользователь лайк
    user_liked = False
    if request.user.is_authenticated:
        user_liked = post.likes.filter(user=request.user).exists()  # Используем связь через related_name='likes'

    user_favorited = post.favorited_by.filter(user=request.user).exists()  # Используем related_name='favorited_by'

    # Получаем все комментарии к посту, отсортированные по времени создания
    all_comments = Comment.objects.filter(post=post).select_related('author').prefetch_related(
        'comment_likes').order_by('created_at')
    # Строим дерево комментариев
    comment_tree = build_comment_tree(all_comments)

    # Подготовим форму комментария
    comment_form = CommentForm(post_id=post_id)
    # Можно передать дополнительные данные, например, комментарии
    return render(request, 'app/post_detail.html', {
        'post': post,
        'user_liked': user_liked,  # Передаём флаг в шаблон
        'comment_form': comment_form,  # Передаём форму в шаблон
        'comment_tree': comment_tree,
        'user_favorited': user_favorited,
    })


@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)  # Предполагается, что у тебя есть PostForm
        if form.is_valid():
            post = form.save(commit=False)  # Не сохраняем в базу пока
            post.author = request.user  # Присваиваем автора текущему пользователю
            post.save()  # Теперь сохраняем
            messages.success(request, 'Пост успешно создан!')
            return redirect('home')  # Перенаправляем на главную страницу после создания
    else:
        form = PostForm()

    return render(request, 'app/post_create.html', {'form': form})


@login_required
def post_delete(request, post_id):
    # Получаем пост или возвращаем 404
    post = get_object_or_404(Post, id=post_id)
    # Проверяем, является ли текущий пользователь автором поста
    if post.author != request.user:
        # Или перенаправляем на главную с сообщением об ошибке
        messages.error(request, 'У вас нет прав для удаления этого поста.')
        return redirect('home')

    if request.method == 'POST':
        # Если это POST-запрос (пользователь подтвердил удаление через модальное окно)
        post_title = post.title  # Сохраняем заголовок для сообщения
        post.delete()  # Удаляем пост из БД (и связанные объекты, если настроено CASCADE)
        messages.success(request, f'Пост "{post_title}" успешно удалён.')
        return redirect('home')  # Перенаправляем на главную страницу

    # Если это GET-запрос (например, прямой доступ по URL),
    # можно перенаправить или показать страницу подтверждения.
    # Обычно для удаления используется POST, но на всякий случай.
    # Лучше перенаправить на детали поста или на главную.
    messages.warning(request, 'Для удаления поста используйте кнопку на странице поста.')
    return redirect('post_detail', post_id=post.id)


@login_required
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    # Получаем или создаём объект Like
    # get_or_create возвращает кортеж (объект, создан ли он)
    like_obj, created = Like.objects.get_or_create(user=request.user, post=post)

    if created:
        # Лайк был добавлен
        action = 'liked'
    else:
        # Лайк уже существовал, значит дизлайкаем
        like_obj.delete()
        action = 'unliked'

    # Сообщение
    messages.info(request, f'Вы {action} пост "{post.title}".')

    # Перенаправляем обратно на страницу поста
    # request.META.get('HTTP_REFERER') возвращает предыдущую страницу
    next_url = request.META.get('HTTP_REFERER', reverse('home'))  # Если реферера нет, идём на главную
    return HttpResponseRedirect(next_url)


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Проверяем авторство
    if post.author != request.user:
        messages.error(request, 'У вас нет прав для редактирования этого поста.')
        return redirect('home')  # Или post_detail

    if request.method == 'POST':
        # Создаём форму с данными из POST-запроса и файлами (если были), привязываем к существующему посту
        form = PostForm(request.POST, request.FILES, instance=post)  # instance=post указывает, какой объект обновлять
        if form.is_valid():
            # form.save() теперь обновит существующий объект post
            form.save()
            messages.success(request, f'Пост "{post.title}" успешно обновлён.')
            # Редиректим на страницу обновлённого поста
            return redirect('post_detail', post_id=post.id)
    else:
        # Для GET-запроса создаём форму с данными существующего поста
        form = PostForm(instance=post)  # instance=post заполняет форму текущими значениями

    return render(request, 'app/post_edit.html', {'form': form, 'post': post})


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == 'POST':
        form = CommentForm(request.POST, post_id=post_id)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post  # Привязываем к посту
            comment.author = request.user  # Привязываем к пользователю
            comment.save()
            messages.success(request, 'Комментарий добавлен.')
            # Редиректим обратно на страницу поста
            return redirect('post_detail', post_id=post.id)
    # Обычно GET-запрос не должен сюда попадать напрямую, но можно перенаправить
    return redirect('post_detail', post_id=post.id)


def build_comment_tree(comments):
    """Вспомогательная функция для построения дерева комментариев."""
    comment_dict = {}
    root_comments = []

    # Сначала создаем словарь всех комментариев по ID
    for comment in comments:
        comment_dict[comment.id] = {'comment': comment, 'replies': []}

    # Затем связываем комментарии с их родителями
    for item in comment_dict.values():
        comment_obj = item['comment']
        if comment_obj.parent_id:
            # Найдем родительский комментарий в словаре
            parent_item = comment_dict.get(comment_obj.parent_id)
            if parent_item:
                parent_item['replies'].append(item)
        else:
            # Это корневой комментарий
            root_comments.append(item)

    return root_comments


@login_required
def profile_view(request, username):
    # Получаем пользователя по username
    user = get_object_or_404(User, username=username)
    # Получаем или создаём профиль
    profile, created = UserProfile.objects.get_or_create(user=user)

    # Передаём и пользователя, и профиль в шаблон
    return render(request, 'app/profile_view.html', {'profile_user': user, 'profile': profile})


@login_required
def profile_edit(request):
    # Получаем профиль текущего пользователя
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлён.')
            # Редиректим на страницу просмотра профиля
            return redirect('profile_view', username=request.user.username)
    else:
        form = UserProfileForm(instance=profile, user=request.user)

    return render(request, 'app/profile_edit.html', {'form': form})


@login_required
def my_posts(request):
    # Получаем только посты текущего пользователя
    posts = Post.objects.filter(author=request.user).select_related('author__profile').prefetch_related('likes',
                                                                                                        'comments')

    # Передаем список posts в шаблон my_posts.html
    context = {
        'posts': posts,
    }
    return render(request, 'app/my_posts.html', context)


@login_required
def favorites(request):
    # Получаем посты, добавленные в избранное текущим пользователем
    # related_name='favorite_posts' позволяет получить Favorite.objects.filter(user=request.user)
    # related_name='favorited_by' позволяет получить Post.objects.filter(favorited_by__user=request.user)
    # Но проще получить объекты Favorite и из них извлечь посты
    favorite_entries = Favorite.objects.filter(user=request.user).select_related(
        'post__author__profile').prefetch_related('post__likes', 'post__comments')
    posts = [entry.post for entry in favorite_entries]  # Извлекаем посты

    context = {
        'posts': posts,  # Передаём список постов
    }
    return render(request, 'app/favorites.html', context)


@login_required
def toggle_favorite(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    # Проверяем, не является ли автор поста текущим пользователем
    if post.author == request.user:
        messages.error(request, 'Нельзя добавить в избранное свой собственный пост.')
        # Редиректим обратно на страницу поста
        next_url = request.META.get('HTTP_REFERER', reverse('home'))
        return HttpResponseRedirect(next_url)

    # Получаем или создаём объект Favorite
    favorite_obj, created = Favorite.objects.get_or_create(user=request.user, post=post)

    if created:
        # Был добавлен в избранное
        action = 'добавлен в'
    else:
        # Уже существовал, значит удаляем
        favorite_obj.delete()
        action = 'удалён из'

    messages.info(request, f'Пост "{post.title}" {action} избранного.')

    # Редиректим обратно на страницу поста
    next_url = request.META.get('HTTP_REFERER', reverse('home'))
    return HttpResponseRedirect(next_url)


@login_required
def messages_list(request, recipient_id=None):
    # Получаем список всех собеседников (людей, с которыми была переписка)
    sent_by_me = Message.objects.filter(sender=request.user).values_list('recipient_id', flat=True)
    sent_to_me = Message.objects.filter(recipient=request.user).values_list('sender_id', flat=True)
    all_contact_ids = set(list(sent_by_me) + list(sent_to_me))
    contacts = User.objects.filter(id__in=all_contact_ids).select_related('profile').distinct()
    # Подсчитываем непрочитанные сообщения *для каждого контакта*
    contacts_with_unread = []
    for contact in contacts:
        unread_count = Message.objects.filter(
            sender=contact,  # Сообщение отправлено *от* этого контакта
            recipient=request.user,  # ... и адресовано *текущему пользователю*
            is_read=False  # ... и *ещё не прочитано*
        ).count()
        contacts_with_unread.append({
            'contact': contact,
            'unread_count': unread_count
        })

    # Сортировка контактов по времени последнего сообщения
    def get_last_message_time(contact):
        last_msg = Message.objects.filter(
            (Q(sender=request.user) & Q(recipient=contact)) |
            (Q(sender=contact) & Q(recipient=request.user))
        ).order_by('-timestamp').first()
        return last_msg.timestamp if last_msg else None

    sorted_contacts_with_unread = sorted(contacts_with_unread, key=lambda x: get_last_message_time(x['contact']),
                                         reverse=True)
    selected_conversation = None
    selected_recipient = None
    if recipient_id:
        selected_recipient = get_object_or_404(User, id=recipient_id)
        if selected_recipient.id in all_contact_ids:
            # Отмечаем сообщения от selected_recipient как прочитанные
            Message.objects.filter(recipient=request.user, sender=selected_recipient, is_read=False).update(
                is_read=True)
            selected_conversation = Message.objects.filter(
                (Q(sender=request.user) & Q(recipient=selected_recipient)) |
                (Q(sender=selected_recipient) & Q(recipient=request.user))
            ).select_related('sender__profile').order_by('timestamp')

    unread_count_total = Message.objects.filter(recipient=request.user, is_read=False).count()
    return render(request, 'app/messages_list.html', {
        'contacts_with_unread': sorted_contacts_with_unread,  # Передаём список словарей
        'selected_conversation': selected_conversation,
        'selected_recipient': selected_recipient,
        'unread_count': unread_count_total,
    })


@login_required
def send_message(request, recipient_id):
    recipient = get_object_or_404(User, id=recipient_id)
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.recipient = recipient
            message.save()
            messages.success(request, f'Сообщение для {recipient.username} отправлено.')
            # Редиректим на страницу с перепиской
            return redirect('messages_list', recipient_id=recipient.id)
    else:
        form = MessageForm()
    if request.method == 'GET':
        return redirect('messages_list', recipient_id=recipient.id)
    return render(request, 'app/send_message.html', {'form': form, 'recipient': recipient})


def shop_home(request):
    products = Product.objects.select_related("category").all()
    categories = Category.objects.all()
    return render(request, 'app/shop/home.html', {
        "products": products,
        "categories": categories,
    })


def shop_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category).select_related("category")
    categories = Category.objects.all()
    return render(request, 'app/shop/category.html', {
        "products": products,
        "category": category,
        "categories": categories,
    })


def shop_product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'app/shop/product_detail.html', {
        "product": product,
    })
