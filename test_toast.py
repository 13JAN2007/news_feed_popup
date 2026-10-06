from windows_toasts import Toast, WindowsToaster

print("Starting...")

toaster = WindowsToaster("Test Notification")

toast = Toast()
toast.text_fields = [
    "Hello Arnav!",
    "Windows Toast test is working."
]

print("Sending toast...")

toaster.show_toast(toast)

print("Toast sent.")