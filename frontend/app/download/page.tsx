import Link from 'next/link';

export default function DownloadPage() {
  return (
    <main className='download-root'>
      <section className='download-shell'>
        <p className='download-kicker'>Safeguard AI Mobile</p>
        <h1>Get real-time alerts wherever you are.</h1>
        <p className='download-copy'>
          Install the app for faster notifications, safer offline guidance, and one-tap SOS dispatch with precise
          location sharing.
        </p>

        <div className='download-cards'>
          <article>
            <strong>Android</strong>
            <p>Recommended for most users in Kenya.</p>
            <a href='#' className='download-primary'>
              Download APK
            </a>
          </article>
          <article>
            <strong>iOS</strong>
            <p>Early access list for App Store release.</p>
            <a href='#' className='download-secondary'>
              Join waitlist
            </a>
          </article>
        </div>

        <div className='download-actions'>
          <Link href='/register' className='download-link'>
            Back to registration
          </Link>
          <Link href='/dashboard' className='download-link'>
            Open live dashboard
          </Link>
        </div>
      </section>
    </main>
  );
}
