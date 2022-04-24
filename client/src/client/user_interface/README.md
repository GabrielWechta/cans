# Usage in code

Instantiate UI object with event loop and a callback queue:

```python
ui = UserInterface(
    loop=event_loop,
    upstream_callback=send_message,
)
```

Create User Models that will be used by chat windows:

```python
eve = UserModel(
    username="Eve",
    id=unique_id,
    color="blue",
)

bob = UserModel(
    username="Bob",
    id=unique_id_2,
    color="red",
)
```

Add chat windows:

```python
ui.view.add_chat(bob)
ui.view.add_chat(eve)
```

Handle incoming message:

```python
ui.on_new_message_received_str(message, user)
```

## To test stuff

```bash
python -m client.user_interface
```

And then try to use keys assigned to commands in `__main__.py`
