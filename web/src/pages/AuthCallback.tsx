import "./Auth.css";
import "./AuthCallback.css";

export default function AuthCallback() {
  return (
    <div className="auth-container">
      <div className="auth-card callback-card">
        <div className="callback-spinner" />
        <h1>로그인 중</h1>
        <p className="subtitle">잠시만 기다려 주세요...</p>
      </div>
    </div>
  );
}
