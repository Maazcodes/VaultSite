import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

import { Results } from './results';
@customElement('search-view')
export class Search extends LitElement {
  static styles = css`
    .search {
      display: flex;
      justify-content: center;
      align-items: baseline;
      margin-bottom: 40px;
    }

    div > input {
      width: 500px;
      margin-top: 28px;
      height: 30px;
      margin-right: 20px;
      border-radius: 4px;
    }

    button {
      background-color: #f9c507;
      display: inline-block;
      height: 30px;
      border-radius: 6px;
    }
  `;

  inputValue:string

  constructor(){
    super()
    this.inputValue = "";
  }

  @property({ type: String }) searchResults = "";

  SearchHandler = async () => {
    // input typed in search bar will be stored in query variable
    const query = this.inputValue
    try {
        const response = await fetch(`http://127.0.0.1:7000/api/search/${query}/`);
        const searchResults = await response.json();
        this.searchResults = searchResults.items
        
      } catch (errors) {
        console.error(errors);
      }
      return "Calling Api";
  }


  render() {

    const inputContent = (event: Event) => {
      const input = event.target as HTMLInputElement;
      this.inputValue = input.value
    }

    const Myresults = this.searchResults
    if(Myresults.length !==0 ){
      new Results(Myresults) // sending search results data to Results Class constructor by creating Results object
    }
   
    return html`
      <div class="search">
        <input @input=${inputContent} type="text" placeholder="Enter Search terms here" />
        <button @click = ${this.SearchHandler}>Search</button>
      </div>
    `;
  }
}