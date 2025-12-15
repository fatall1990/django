from django.db import models
from django.contrib.auth.models import User
from PIL import Image
import os


class Post(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)  # blank=True позволяет не заполнять поле

    def __str__(self):
        return self.title

    def get_like_count(self):
        """Возвращает количество лайков для поста."""
        return self.likes.count()

    def user_liked(self, user):
        """Проверяет, поставил ли конкретный пользователь лайк."""
        return self.likes.filter(user=user).exists()

    def get_comment_count(self):  # <-- Новый метод
        """Возвращает количество комментариев для поста."""
        return self.comments.count()

    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'

    # Два нижних метода по желанию
    # Переопределяем метод delete() для удаления файла
    def delete(self, *args, **kwargs):
        # Если есть изображение и оно существует на диске
        if self.image and os.path.isfile(self.image.path):
            os.remove(self.image.path)  # Удаляем файл с диска
        super().delete(*args, **kwargs)  # Вызываем родительский delete() для удаления из БД

    # Переопределяем метод save() для удаления старого файла при обновлении
    def save(self, *args, **kwargs):
        # Если объект уже существует в базе данных (то есть редактируется)
        if self.pk:  # pk — первичный ключ, если он есть — объект уже сохранён
            old_post = Post.objects.get(pk=self.pk)
            # Если поле image изменилось (новый файл загружен)
            if old_post.image and old_post.image != self.image:
                # Удаляем старый файл
                if os.path.isfile(old_post.image.path):
                    os.remove(old_post.image.path)
        # Сохраняем объект
        super().save(*args, **kwargs)


# Модель для лайков
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post') # Один пользователь может лайкнуть пост только один раз
        verbose_name = 'Like'
        verbose_name_plural = 'Likes'

    def __str__(self):
        return f"{self.user.username} liked {self.post.title}"


# Модель для комментариев
class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    #.CASCADE удалит комментарии при удалении поста
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Поле для вложенности (ответ на комментарий)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    # CASCADE удалит ответы при удалении родителя

    def __str__(self):
        return f'Comment by {self.author.username} on {self.post.title}'

    class Meta:
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'


# Модель для лайков к комментариям (пока не реализовано)
class CommentLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_likes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='comment_likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')
        verbose_name = 'CommentLike'
        verbose_name_plural = 'CommentLikes'

    def __str__(self):
        return f"{self.user.username} liked comment on {self.comment.post.title}"


# Новая модель для профиля пользователя
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    bio = models.TextField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Опционально: обработка изображения (уменьшение размера)
        if self.avatar:
            img = Image.open(self.avatar.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.avatar.path)

    class Meta:
        verbose_name = 'UserProfile'
        verbose_name_plural = 'UserProfiles'


# Модель для избранного
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post') # Один пользователь может добавить пост в избранное только один раз
        verbose_name = 'Favorite'
        verbose_name_plural = 'Favorites'
        # Сортировка по умолчанию по дате добавления (новые первыми)
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} favorited {self.post.title}"


# модель для личных сообщений
class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200, blank=True) # Тема сообщения (опционально)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False) # Флаг прочтения

    def __str__(self):
        return f'Сообщение от {self.sender.username} для {self.recipient.username}'

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['-timestamp']


# Модель для категорий
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'


# Модель для товара
class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="product_images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
