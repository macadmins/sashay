Sashay is a log scraper and parser that, when you turn up verbosity on a Mac running Server.app's Caching service, sends you reports. It is written in python, requires just the server app itself so you don't need SMTP, and borrows heavily from ideas started in @erikng's [Cacher](https://github.com/erikng/Cacher). You can customize which types of downloads it tells you about, the time period it operates on, and scheduling it is easy with the included launchdaemons.
![Example sashay report](sashay.png)
You should make sure you're running Server.app version 4.1 or greater, and that you've enabled the verbose logging with ```sudo serveradmin settings caching:LogClientIdentity = 1```

Hope you find it useful!
