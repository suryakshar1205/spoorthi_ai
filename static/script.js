const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const chatMessages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");
const apiBase =
  window.SPOORTHI_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:5000`;

function appendMessage(role, text, extraClass = "") {
  const message = document.createElement("div");
  message.className = `message ${role} ${extraClass}`.trim();

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  message.appendChild(bubble);
  chatMessages.appendChild(message);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return message;
}

async function sendMessage(content) {
  const typingNode = appendMessage("bot", "Typing...", "typing");
  sendButton.disabled = true;

  try {
    const response = await fetch(`${apiBase}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: content }),
    });

    let payload = { answer: "Something went wrong." };
    try {
      payload = await response.json();
    } catch (error) {
      payload = { answer: "Something went wrong." };
    }

    typingNode.remove();
    appendMessage("bot", response.ok ? payload.answer : "Something went wrong.");
  } catch (error) {
    typingNode.remove();
    appendMessage("bot", "Something went wrong.");
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = messageInput.value.trim();
  if (!content) {
    return;
  }

  appendMessage("user", content);
  messageInput.value = "";
  messageInput.style.height = "58px";
  await sendMessage(content);
});

messageInput.addEventListener("input", () => {
  messageInput.style.height = "58px";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 180)}px`;
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

messageInput.focus();
