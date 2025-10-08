let currentMailbox = 'inbox';

document.addEventListener('DOMContentLoaded', () => {
  document.querySelector('#inbox').addEventListener('click', () => load_mailbox('inbox'));
  document.querySelector('#sent').addEventListener('click', () => load_mailbox('sent'));
  document.querySelector('#archived').addEventListener('click', () => load_mailbox('archive'));
  document.querySelector('#compose').addEventListener('click', () => compose_email());
  document.querySelector('#compose-form').addEventListener('submit', send_email);

  load_mailbox('inbox');
});

function compose_email(prefill = {}) {
  hide_alert();
  document.querySelector('#emails-view').style.display = 'none';
  document.querySelector('#compose-view').style.display = 'block';

  document.querySelector('#compose-recipients').value = prefill.recipients || '';
  document.querySelector('#compose-subject').value = prefill.subject || '';
  document.querySelector('#compose-body').value = prefill.body || '';

  if (prefill.focusBody) {
    document.querySelector('#compose-body').focus();
  } else {
    document.querySelector('#compose-recipients').focus();
  }
}

function load_mailbox(mailbox) {
  currentMailbox = mailbox;
  hide_alert();

  const emailsView = document.querySelector('#emails-view');
  const composeView = document.querySelector('#compose-view');
  emailsView.style.display = 'block';
  composeView.style.display = 'none';

  emailsView.innerHTML = '';
  const heading = document.createElement('h3');
  heading.textContent = mailbox.charAt(0).toUpperCase() + mailbox.slice(1);
  emailsView.appendChild(heading);

  const listContainer = document.createElement('div');
  listContainer.className = 'list-group mailbox-list';
  emailsView.appendChild(listContainer);

  fetch(`/emails/${mailbox}`)
    .then(response => response.json()
      .then(data => ({ ok: response.ok, data }))
    )
    .then(({ ok, data }) => {
      if (!ok) {
        throw new Error(data.error || 'Unable to load mailbox.');
      }

      if (data.length === 0) {
        const emptyState = document.createElement('div');
        emptyState.className = 'alert alert-info mt-3';
        emptyState.textContent = 'No emails to display.';
        emailsView.appendChild(emptyState);
        return;
      }

      data.forEach(email => {
        const item = document.createElement('button');
        item.className = `list-group-item list-group-item-action email-row d-flex justify-content-between align-items-center`;
        item.classList.toggle('email-read', email.read);

        const counterpart = mailbox === 'sent'
          ? email.recipients.join(', ')
          : email.sender;

        const subject = email.subject || '(no subject)';

        const meta = document.createElement('div');
        meta.className = 'email-meta';
        meta.innerHTML = `
          <span class="email-counterpart">${counterpart}</span>
          <span class="email-subject">${subject}</span>
        `;

        const timestamp = document.createElement('span');
        timestamp.className = 'email-timestamp text-muted';
        timestamp.textContent = email.timestamp;

        item.appendChild(meta);
        item.appendChild(timestamp);

        item.addEventListener('click', () => view_email(email.id));
        listContainer.appendChild(item);
      });
    })
    .catch(error => {
      show_alert(error.message);
    });
}

function send_email(event) {
  event.preventDefault();
  hide_alert();

  const recipients = document.querySelector('#compose-recipients').value.trim();
  const subject = document.querySelector('#compose-subject').value;
  const body = document.querySelector('#compose-body').value;

  fetch('/emails', {
    method: 'POST',
    body: JSON.stringify({ recipients, subject, body }),
  })
    .then(response => response.json()
      .then(data => ({ ok: response.ok, data }))
    )
    .then(({ ok, data }) => {
      if (!ok) {
        throw new Error(data.error || 'Unable to send email.');
      }

      show_alert('Email sent successfully.', 'success');
      load_mailbox('sent');
    })
    .catch(error => {
      show_alert(error.message, 'danger');
    });
}

function view_email(emailId) {
  hide_alert();

  fetch(`/emails/${emailId}`)
    .then(response => response.json()
      .then(data => ({ ok: response.ok, data }))
    )
    .then(({ ok, data }) => {
      if (!ok) {
        throw new Error(data.error || 'Unable to load email.');
      }

      const emailsView = document.querySelector('#emails-view');
      emailsView.innerHTML = '';

      const header = document.createElement('div');
      header.className = 'email-details card';

      const body = document.createElement('div');
      body.className = 'card-body';
      body.innerHTML = `
        <p><strong>From:</strong> ${data.sender}</p>
        <p><strong>To:</strong> ${data.recipients.join(', ')}</p>
        <p><strong>Subject:</strong> ${data.subject || '(no subject)'}</p>
        <p><strong>Timestamp:</strong> ${data.timestamp}</p>
      `;

      const actions = document.createElement('div');
      actions.className = 'email-actions btn-toolbar mb-3';

      const replyButton = document.createElement('button');
      replyButton.className = 'btn btn-outline-primary mr-2';
      replyButton.textContent = 'Reply';
      replyButton.addEventListener('click', () => {
        const userEmail = document.body.dataset.userEmail || '';
        const recipients = data.sender;
        let subject = data.subject || '';
        const normalizedSubject = subject.trim().toLowerCase();
        if (!normalizedSubject.startsWith('re:')) {
          subject = `Re: ${subject}`.trim();
        }
        const quotedBody = `On ${data.timestamp} ${data.sender} wrote:\n${data.body}\n\n`;
        compose_email({
          recipients,
          subject,
          body: `\n\n${quotedBody}`,
          focusBody: true,
        });
      });
      actions.appendChild(replyButton);

      const userEmail = document.body.dataset.userEmail || '';
      if (data.sender !== userEmail) {
        const archiveButton = document.createElement('button');
        archiveButton.className = 'btn btn-outline-secondary';
        archiveButton.textContent = data.archived ? 'Unarchive' : 'Archive';
        archiveButton.addEventListener('click', () =>
          toggle_archive(emailId, !data.archived)
        );
        actions.appendChild(archiveButton);
      }

      body.appendChild(actions);

      const messageBody = document.createElement('div');
      messageBody.className = 'email-body';
      messageBody.textContent = data.body || '';

      header.appendChild(body);
      header.appendChild(document.createElement('hr'));
      header.appendChild(messageBody);
      emailsView.appendChild(header);

      if (!data.read) {
        mark_read(emailId);
      }
    })
    .catch(error => {
      show_alert(error.message, 'danger');
    });
}

function mark_read(emailId) {
  fetch(`/emails/${emailId}`, {
    method: 'PUT',
    body: JSON.stringify({ read: true }),
  }).catch(() => {});
}

function toggle_archive(emailId, archived) {
  fetch(`/emails/${emailId}`, {
    method: 'PUT',
    body: JSON.stringify({ archived }),
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Unable to update archive state.');
      }
      load_mailbox(archived ? 'archive' : 'inbox');
    })
    .catch(error => {
      show_alert(error.message, 'danger');
    });
}

function show_alert(message, type = 'info') {
  const container = document.querySelector('#alert-container');
  if (!container) {
    if (message) {
      alert(message);
    }
    return;
  }
  container.innerHTML = '';
  if (!message) {
    return;
  }
  const alert = document.createElement('div');
  alert.className = `alert alert-${type}`;
  alert.textContent = message;
  container.appendChild(alert);
}

function hide_alert() {
  show_alert('');
}
