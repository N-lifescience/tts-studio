import { useEffect, useRef } from 'react'

interface Props {
  title: string
  onCancel: () => void
  onDelete: () => void
}

export function DeleteProjectDialog({ title, onCancel, onDelete }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    dialog.current?.showModal()
  }, [])

  return (
    <dialog
      ref={dialog}
      className="delete-dialog"
      aria-labelledby="delete-project-heading"
      aria-describedby="delete-project-description"
      onCancel={(e) => {
        e.preventDefault()
        onCancel()
      }}
    >
      <h2 id="delete-project-heading">에피소드를 삭제할까요?</h2>
      <p className="delete-project-name">{title}</p>
      <p id="delete-project-description">
        대본과 만든 음성은 복구할 수 있도록 보관합니다. iCloud로 내보낸 파일은 그대로 남습니다.
      </p>
      <div className="dialog-actions">
        <button className="btn" autoFocus onClick={onCancel}>취소</button>
        <button className="btn danger" onClick={onDelete}>삭제</button>
      </div>
    </dialog>
  )
}
