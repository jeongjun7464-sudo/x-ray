import { render,screen } from '@testing-library/react'; import {describe,it,expect} from 'vitest'; import App from './App';
describe('App',()=>{it('shows upload workflow and disclaimer',()=>{render(<App/>);expect(screen.getByText('영상 업로드')).toBeInTheDocument();expect(screen.getByText('연구·교육용 보조 시스템')).toBeInTheDocument()})})
