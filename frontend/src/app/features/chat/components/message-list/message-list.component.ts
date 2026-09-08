import { ChangeDetectionStrategy, Component, Input } from '@angular/core';

import { ChatMessage } from '@core/models/chat.model';

@Component({
  selector: 'app-message-list',
  standalone: true,
  imports: [],
  templateUrl: './message-list.component.html',
  styleUrl: './message-list.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MessageListComponent {
  @Input() messages: ChatMessage[] = [];
  @Input() pending = false;
  @Input() progressLabel: string | null = null;
}
