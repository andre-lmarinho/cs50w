(() => {
  const pageRoot = document.querySelector('#page-root');
  if (!pageRoot) return;

  const feed = pageRoot.dataset.feed || 'all';
  const profileUsername = pageRoot.dataset.profile || '';

  let currentPage = 1;
  let totalPages = 1;

  const postsContainer = document.querySelector('#posts-container');
  const paginationContainer = document.querySelector('#pagination');
  const alertContainer = document.querySelector('#alert-container');
  const newPostForm = document.querySelector('#new-post-form');
  const newPostContent = document.querySelector('#new-post-content');
  const charCount = document.querySelector('#char-count');
  const followToggle = document.querySelector('#follow-toggle');
  const profileHeader = document.querySelector('#profile-header');

  document.addEventListener('DOMContentLoaded', () => {
    if (newPostForm && newPostContent) {
      newPostForm.addEventListener('submit', handleNewPostSubmit);
      newPostContent.addEventListener('input', updateCharCount);
      updateCharCount();
    }

    if (followToggle && profileUsername) {
      followToggle.addEventListener('click', toggleFollow);
    }

    loadFeed();

    if (profileHeader && profileUsername) {
      loadProfileInfo();
    }
  });

  function updateCharCount() {
    if (!charCount || !newPostContent) return;
    charCount.textContent = newPostContent.value.length.toString();
  }

  function getCSRFToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function showAlert(message, type = 'info') {
    if (!alertContainer) return;
    alertContainer.innerHTML = '';
    if (!message) return;
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    alertContainer.appendChild(alert);
  }

  async function loadFeed(page = 1) {
    currentPage = page;
    showAlert('');
    postsContainer.innerHTML = '<div class="text-center py-4 text-muted">Loading...</div>';
    paginationContainer.innerHTML = '';

    const params = new URLSearchParams({ feed, page: page.toString() });
    if (feed === 'profile' && profileUsername) {
      params.append('username', profileUsername);
    }

    try {
      const response = await fetch(`/api/posts?${params.toString()}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Unable to load posts.');
      }

      totalPages = data.total_pages || 1;
      renderPosts(data.results || []);
      renderPagination();
    } catch (error) {
      postsContainer.innerHTML = '';
      showAlert(error.message, 'danger');
    }
  }

  function renderPosts(posts) {
    postsContainer.innerHTML = '';

    if (!posts.length) {
      postsContainer.innerHTML = '<div class="text-center py-4 text-muted">No posts to display.</div>';
      return;
    }

    posts.forEach((post) => {
      const item = document.createElement('div');
      item.className = 'list-group-item post-item';
      item.dataset.postId = post.id;

      const header = document.createElement('div');
      header.className = 'd-flex justify-content-between align-items-center mb-2';

      const authorLink = document.createElement('a');
      authorLink.href = `/profile/${post.author}/`;
      authorLink.textContent = post.author;
      authorLink.className = 'font-weight-bold';

      const timestamp = document.createElement('span');
      timestamp.className = 'text-muted small';
      timestamp.textContent = post.created_at_display || '';

      header.appendChild(authorLink);
      header.appendChild(timestamp);

      const content = document.createElement('p');
      content.className = 'mb-2 post-content';
      content.textContent = post.content;

      item.appendChild(header);
      item.appendChild(content);

      const footer = document.createElement('div');
      footer.className = 'd-flex align-items-center justify-content-between';

      const actions = document.createElement('div');
      actions.className = 'btn-group';

      if (post.can_edit) {
        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm btn-outline-secondary';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => enterEditMode(item, post));
        actions.appendChild(editBtn);
      }

      const likeBtn = document.createElement('button');
      likeBtn.className = `btn btn-sm ${post.liked ? 'btn-primary' : 'btn-outline-primary'}`;
      likeBtn.innerHTML = `Like (<span class="like-count">${post.like_count}</span>)`;
      likeBtn.addEventListener('click', () => toggleLike(post.id, likeBtn));

      footer.appendChild(actions);
      footer.appendChild(likeBtn);

      item.appendChild(footer);
      postsContainer.appendChild(item);
    });
  }

  function renderPagination() {
    paginationContainer.innerHTML = '';
    if (totalPages <= 1) return;

    const createPageItem = (label, page, disabled = false, active = false) => {
      const li = document.createElement('li');
      li.className = `page-item${disabled ? ' disabled' : ''}${active ? ' active' : ''}`;
      const a = document.createElement('button');
      a.className = 'page-link';
      a.type = 'button';
      a.textContent = label;

      if (!disabled && !active) {
        a.addEventListener('click', () => loadFeed(page));
      }

      li.appendChild(a);
      return li;
    };

    paginationContainer.appendChild(
      createPageItem('Previous', currentPage - 1, currentPage === 1)
    );

    for (let page = 1; page <= totalPages; page += 1) {
      paginationContainer.appendChild(
        createPageItem(page, page, false, page === currentPage)
      );
    }

    paginationContainer.appendChild(
      createPageItem('Next', currentPage + 1, currentPage === totalPages)
    );
  }

  async function handleNewPostSubmit(event) {
    event.preventDefault();
    if (!newPostContent) return;
    const content = newPostContent.value.trim();
    if (!content) {
      showAlert('Post content cannot be empty.', 'warning');
      return;
    }

    try {
      const response = await fetch('/api/posts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({ content }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to create post.');

      newPostContent.value = '';
      updateCharCount();
      showAlert('Post published!', 'success');
      loadFeed(1);
    } catch (error) {
      showAlert(error.message, 'danger');
    }
  }

  function enterEditMode(postElement, postData) {
    const contentPara = postElement.querySelector('.post-content');
    if (!contentPara) return;

    const originalText = contentPara.textContent;
    const textarea = document.createElement('textarea');
    textarea.className = 'form-control mb-2';
    textarea.value = originalText;
    textarea.rows = Math.max(3, Math.ceil(originalText.length / 80));

    const buttonGroup = document.createElement('div');
    buttonGroup.className = 'btn-group btn-group-sm';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-primary';
    saveBtn.textContent = 'Save';

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn btn-outline-secondary';
    cancelBtn.textContent = 'Cancel';

    saveBtn.addEventListener('click', async () => {
      const updatedContent = textarea.value.trim();
      if (!updatedContent) {
        showAlert('Post content cannot be empty.', 'warning');
        return;
      }
      if (updatedContent === originalText) {
        exitEditMode();
        return;
      }
      try {
        const response = await fetch(`/api/posts/${postData.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
          },
          body: JSON.stringify({ content: updatedContent }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Unable to update post.');

        contentPara.textContent = data.content;
        showAlert('Post updated.', 'success');
        exitEditMode();
      } catch (error) {
        showAlert(error.message, 'danger');
      }
    });

    cancelBtn.addEventListener('click', exitEditMode);

    buttonGroup.appendChild(saveBtn);
    buttonGroup.appendChild(cancelBtn);

    contentPara.replaceWith(textarea);
    const footer = postElement.querySelector('.btn-group');
    if (footer) {
      footer.innerHTML = '';
      footer.appendChild(buttonGroup);
    }

    textarea.focus();

    function exitEditMode() {
      textarea.replaceWith(contentPara);
      contentPara.textContent = originalText;
      if (footer) {
        footer.innerHTML = '';
        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm btn-outline-secondary';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', () => enterEditMode(postElement, postData));
        footer.appendChild(editBtn);
      }
      loadFeed(currentPage);
    }
  }

  async function toggleLike(postId, buttonElement) {
    try {
      const response = await fetch(`/api/posts/${postId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({ toggle_like: true }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to update like.');

      const likeCountSpan = buttonElement.querySelector('.like-count');
      if (likeCountSpan) {
        likeCountSpan.textContent = data.like_count;
      }
      buttonElement.className = `btn btn-sm ${data.liked ? 'btn-primary' : 'btn-outline-primary'}`;
    } catch (error) {
      showAlert(error.message, 'danger');
    }
  }

  async function loadProfileInfo() {
    try {
      const response = await fetch(`/api/profile/${profileUsername}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load profile.');

      const usernameEl = document.querySelector('#profile-username');
      const followersEl = document.querySelector('#profile-followers');
      const followingEl = document.querySelector('#profile-following');
      const followersPluralEl = document.querySelector('#profile-followers-plural');

      if (usernameEl) usernameEl.textContent = data.username;
      if (followersEl) followersEl.textContent = data.followers;
      if (followingEl) followingEl.textContent = data.following;
      if (followersPluralEl) {
        followersPluralEl.textContent = data.followers === 1 ? '' : 's';
      }

      if (followToggle) {
        if (data.is_self) {
          followToggle.style.display = 'none';
        } else {
          followToggle.style.display = 'inline-block';
          followToggle.textContent = data.is_following ? 'Unfollow' : 'Follow';
          followToggle.dataset.following = data.is_following ? 'true' : 'false';
        }
      }
    } catch (error) {
      showAlert(error.message, 'danger');
    }
  }

  async function toggleFollow() {
    if (!followToggle) return;
    followToggle.disabled = true;
    try {
      const response = await fetch(`/api/profile/${profileUsername}/follow`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken(),
        },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to update follow state.');

      followToggle.textContent = data.is_following ? 'Unfollow' : 'Follow';
      followToggle.dataset.following = data.is_following ? 'true' : 'false';

      const followersEl = document.querySelector('#profile-followers');
      const followersPluralEl = document.querySelector('#profile-followers-plural');
      if (followersEl) followersEl.textContent = data.followers;
      if (followersPluralEl) {
        followersPluralEl.textContent = data.followers === 1 ? '' : 's';
      }

      showAlert(data.is_following ? 'Now following user.' : 'Unfollowed user.', 'success');
      loadFeed(1);
    } catch (error) {
      showAlert(error.message, 'danger');
    } finally {
      followToggle.disabled = false;
    }
  }
})();
